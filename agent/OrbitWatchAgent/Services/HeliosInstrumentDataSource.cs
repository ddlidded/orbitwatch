using System.Collections.Concurrent;
using System.Globalization;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Threading.Channels;
using System.Xml;
using Microsoft.Win32;
using Thermo.Interfaces.ExplorisAccess_V1;
using Thermo.Interfaces.ExplorisAccess_V1.Control.Acquisition;
using Thermo.Interfaces.ExplorisAccess_V1.MsScanContainer;
using Thermo.Interfaces.InstrumentAccess_V1;
using Thermo.Interfaces.InstrumentAccess_V1.Control.Acquisition;
using Thermo.Interfaces.InstrumentAccess_V1.MsScanContainer;
using Thermo.Interfaces.SpectrumFormat_V1;

namespace OrbitWatchAgent.Services;

public sealed class HeliosInstrumentDataSource : IInstrumentDataSource, IDisposable
{
    private readonly ILogger<HeliosInstrumentDataSource> _logger;
    private readonly IConfiguration _config;
    private readonly ConcurrentDictionary<string, double> _latestTelemetry = new();
    private readonly Channel<TelemetryEvent> _telemetryChannel = Channel.CreateUnbounded<TelemetryEvent>();
    private IExplorisInstrumentAccessContainer? _container;
    private IExplorisInstrumentAccess? _instrument;
    private IExplorisMsScanContainer? _scanContainer;
    private readonly List<IDisposable> _subscriptions = new();
    private bool _disposed;

    // Current acquisition context. Updated when an acquisition stream opens so scans are
    // attributed to the correct Xcalibur sequence/sample as the run progresses.
    private string _currentSequenceId = "";
    private string _currentSequenceName = "";
    private string _currentSampleId = "";
    private string _currentSampleName = "";
    private string _currentSamplePolarity = "positive";

    public HeliosInstrumentDataSource(ILogger<HeliosInstrumentDataSource> logger, IConfiguration config)
    {
        _logger = logger;
        _config = config;
        _currentSequenceId = config.GetValue<string>("Agent:Sequence:ExternalId") ?? "SEQ-HELIOS-001";
        _currentSampleId = config.GetValue<string>("Agent:Sample:ExternalId") ?? "SMP-001";
    }

    public Task<InstrumentIdentity> GetInstrumentIdentityAsync(CancellationToken cancellationToken = default)
    {
        EnsureConnected();
        var name = _config.GetValue<string>("Agent:Instrument:Name");
        var serial = _config.GetValue<string>("Agent:Instrument:Serial");
        if (_instrument is not null)
        {
            try { name = _instrument.InstrumentName; } catch (Exception ex) { _logger.LogWarning(ex, "Unable to read instrument name"); }
        }

        return Task.FromResult(new InstrumentIdentity(
            serial ?? "UNKNOWN",
            name ?? _config.GetValue<string>("Agent:Instrument:Name") ?? "Exploris 480",
            _config.GetValue<string>("Agent:Instrument:Model") ?? "Orbitrap Exploris 480",
            _config.GetValue<string>("Agent:Instrument:ApiVersion"),
            _config.GetValue<string>("Agent:Instrument:TuneVersion"),
            _config.GetValue<string>("Agent:Instrument:IapiVersion")
        ));
    }

    public async Task<SequenceSnapshot> GetSequenceSnapshotAsync(CancellationToken cancellationToken = default)
    {
        EnsureConnected();

        // Prefer the Xcalibur sequence file referenced by the active acquisition state.
        var fileSnapshot = ReadXcaliburSequenceFromState();
        if (fileSnapshot is not null)
        {
            _logger.LogInformation(
                "Loaded Xcalibur sequence \"{SequenceName}\" with {SampleCount} samples from sequence file.",
                fileSnapshot.SequenceName,
                fileSnapshot.Samples.Count);
            _currentSequenceId = fileSnapshot.ExternalSequenceId;
            _currentSequenceName = fileSnapshot.SequenceName;
            if (fileSnapshot.Samples.Count > 0)
            {
                _currentSampleId = fileSnapshot.Samples[0].ExternalSampleId;
                _currentSampleName = fileSnapshot.Samples[0].SampleName;
            }
            return fileSnapshot;
        }

        // Fallback: wait for the next acquisition stream opening event (one sample).
        var tcs = new TaskCompletionSource<SequenceSnapshot>(TaskCreationOptions.RunContinuationsAsynchronously);

        EventHandler<ExplorisAcquisitionOpeningEventArgs>? handler = null;
        handler = (sender, e) =>
        {
            var snapshot = ParseAcquisitionOpening(e.StartingInformation);
            ApplyAcquisitionContext(e.StartingInformation);
            tcs.TrySetResult(snapshot);
        };

        try
        {
            _instrument!.Control.Acquisition.AcquisitionStreamOpening += handler;
            using var registration = cancellationToken.Register(() => tcs.TrySetCanceled());
            return await tcs.Task.WaitAsync(TimeSpan.FromSeconds(10), cancellationToken);
        }
        catch (TimeoutException)
        {
            _logger.LogWarning("No acquisition stream opening within timeout; returning default sequence snapshot.");
            return DefaultSequenceSnapshot();
        }
        finally
        {
            if (handler is not null)
                _instrument!.Control.Acquisition.AcquisitionStreamOpening -= handler;
        }
    }

    public async IAsyncEnumerable<ScanEvent> StreamScansAsync(string? externalSampleId = null, [EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        EnsureConnected();
        var channel = Channel.CreateUnbounded<ScanEvent>();

        var targetSampleId = externalSampleId ?? _currentSampleId;
        var streaming = false;

        EventHandler<ExplorisAcquisitionOpeningEventArgs>? openingHandler = null;
        EventHandler? closingHandler = null;
        EventHandler<ExplorisMsScanEventArgs>? scanHandler = null;

        openingHandler = (sender, e) =>
        {
            ApplyAcquisitionContext(e.StartingInformation);
            if (string.IsNullOrWhiteSpace(targetSampleId) || _currentSampleId == targetSampleId)
            {
                streaming = true;
            }
            else if (streaming)
            {
                // A new sample has started; stop streaming the current target.
                streaming = false;
                channel.Writer.TryComplete();
            }
        };

        closingHandler = (sender, e) =>
        {
            streaming = false;
            channel.Writer.TryComplete();
        };

        scanHandler = (sender, e) =>
        {
            try
            {
                if (!streaming) return;
                if (e.GetScan() is not IMsScan scan) return;
                using (scan)
                {
                    var ev = ConvertScan(scan);
                    if (ev is not null)
                    {
                        channel.Writer.TryWrite(ev);
                        ExtractTelemetry(scan);
                    }
                }
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to convert scan.");
            }
        };

        _scanContainer = _instrument!.GetMsScanContainer(0) as IExplorisMsScanContainer;
        if (_scanContainer is null)
        {
            _logger.LogError("Unable to get MS scan container.");
            yield break;
        }

        // If an acquisition is already open for the target, start streaming immediately.
        var current = TryReadCurrentSampleFromState();
        if (current is not null && (string.IsNullOrWhiteSpace(targetSampleId) || current.ExternalSampleId == targetSampleId))
        {
            _currentSequenceId = current.ExternalSampleId;
            _currentSampleId = current.ExternalSampleId;
            _currentSampleName = current.SampleName;
            if (!string.IsNullOrWhiteSpace(current.Polarity)) _currentSamplePolarity = current.Polarity;
            streaming = true;
        }

        _instrument.Control.Acquisition.AcquisitionStreamOpening += openingHandler;
        _instrument.Control.Acquisition.AcquisitionStreamClosing += closingHandler;
        _scanContainer.MsScanArrived += scanHandler;
        _subscriptions.Add(new ActionDisposable(() =>
        {
            _instrument.Control.Acquisition.AcquisitionStreamOpening -= openingHandler;
            _instrument.Control.Acquisition.AcquisitionStreamClosing -= closingHandler;
            _scanContainer!.MsScanArrived -= scanHandler;
        }));

        await foreach (var item in channel.Reader.ReadAllAsync(cancellationToken))
        {
            yield return item;
        }
    }

    public async IAsyncEnumerable<TelemetryEvent> StreamTelemetryAsync([EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        await foreach (var ev in _telemetryChannel.Reader.ReadAllAsync(cancellationToken))
        {
            yield return ev;
        }
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        foreach (var sub in _subscriptions) sub.Dispose();
        _container?.Dispose();
        _telemetryChannel.Writer.Complete();
    }

    private void EnsureConnected()
    {
        if (_container is not null) return;
        if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
            throw new PlatformNotSupportedException("The Thermo IAPI adapter requires Windows with Tune/IAPI installed.");

        _container = CreateContainer();
        _container.StartOnlineAccess();
        _instrument = _container.Get(1) as IExplorisInstrumentAccess;
        if (_instrument is null)
            throw new InvalidOperationException("Unable to get Exploris instrument access.");
    }

    [SupportedOSPlatform("windows")]
    private static IExplorisInstrumentAccessContainer CreateContainer()
    {
        const string defaultRegistry = "SOFTWARE\\Thermo Exploris";
        const string defaultBasePath = "Thermo\\Exploris";
        const string xmlRoot = "DataSystem";
        const string apiFileNameDescriptor = "ApiFileName";
        const string apiClassNameDescriptor = "ApiClassName";

        string? basePath = null;
        using (var key = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64))
        using (var sub = key.OpenSubKey(defaultRegistry))
        {
            basePath = sub?.GetValue("data") as string;
        }

        if (string.IsNullOrEmpty(basePath) || !File.Exists(Path.Combine(basePath, $"{xmlRoot}.xml")))
        {
            basePath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), defaultBasePath);
        }

        var xmlPath = Path.Combine(basePath, $"{xmlRoot}.xml");
        if (!File.Exists(xmlPath))
            throw new FileNotFoundException($"Exploris DataSystem XML not found at {xmlPath}");

        var doc = new XmlDocument();
        doc.Load(xmlPath);
        var root = doc[xmlRoot] ?? throw new InvalidOperationException("DataSystem root missing.");
        var filename = root[apiFileNameDescriptor]?.InnerText?.Trim() ?? throw new InvalidOperationException("ApiFileName missing.");
        var classname = root[apiClassNameDescriptor]?.InnerText?.Trim() ?? throw new InvalidOperationException("ApiClassName missing.");

        var container = File.Exists(filename)
            ? Assembly.LoadFrom(filename).CreateInstance(classname, true)
            : Assembly.Load(filename).CreateInstance(classname, true);
        return container as IExplorisInstrumentAccessContainer
            ?? throw new InvalidOperationException($"Unable to create {classname}.");
    }

    private SequenceSnapshot? ReadXcaliburSequenceFromState()
    {
        try
        {
            var state = _instrument?.Control?.Acquisition?.State;
            if (state is null) return null;

            var sequenceFileName = GetProperty<string>(state, "SequenceFileName");
            var sequenceFileIndex = GetProperty<int?>(state, "SequenceFileIndex");
            var methodName = GetProperty<string>(state, "MethodName");

            if (string.IsNullOrWhiteSpace(sequenceFileName) || !File.Exists(sequenceFileName))
                return null;

            var samples = ParseTextSequenceFile(sequenceFileName);
            if (samples is null || samples.Count == 0)
            {
                // The file may be a binary SLD that we cannot parse; at least surface the active row.
                var activeId = sequenceFileIndex.HasValue ? $"SMP-{sequenceFileIndex.Value:0000}" : "SMP-0001";
                samples = new List<SampleInfo>
                {
                    new(activeId, sequenceFileIndex ?? 1, activeId, "Unknown", methodName, "positive", null, null, null)
                };
            }

            var sequenceName = Path.GetFileNameWithoutExtension(sequenceFileName);
            var externalId = _config.GetValue<string>("Agent:Sequence:ExternalId") ?? sequenceName;

            return new SequenceSnapshot(externalId, sequenceName, samples);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to read Xcalibur sequence from instrument state.");
            return null;
        }
    }

    private SampleInfo? TryReadCurrentSampleFromState()
    {
        try
        {
            var state = _instrument?.Control?.Acquisition?.State;
            if (state is null) return null;

            var sequenceFileName = GetProperty<string>(state, "SequenceFileName");
            var sequenceFileIndex = GetProperty<int?>(state, "SequenceFileIndex");
            if (string.IsNullOrWhiteSpace(sequenceFileName) || !sequenceFileIndex.HasValue)
                return null;

            var samples = ParseTextSequenceFile(sequenceFileName);
            if (samples is null || samples.Count == 0)
            {
                var activeId = $"SMP-{sequenceFileIndex.Value:0000}";
                return new SampleInfo(activeId, sequenceFileIndex.Value, activeId, "Unknown", null, "positive", null, null, null);
            }

            var idx = Math.Max(0, Math.Min(sequenceFileIndex.Value - 1, samples.Count - 1));
            return samples[idx];
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to read current sample from instrument state.");
            return null;
        }
    }

    private List<SampleInfo>? ParseTextSequenceFile(string path)
    {
        try
        {
            var bytes = File.ReadAllBytes(path);
            // Reject obvious binary files.
            if (bytes.Length > 0 && bytes.Any(b => b == 0))
                return null;

            var text = File.ReadAllText(path);
            var lines = text.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries)
                .Where(l => !string.IsNullOrWhiteSpace(l))
                .ToList();

            if (lines.Count < 2)
                return null;

            // Try to detect a header line with known Xcalibur sequence columns.
            var headerLine = lines[0];
            var delimiter = new[] { '\t' };
            if (!headerLine.Contains('\t'))
            {
                if (headerLine.Contains(',')) delimiter = new[] { ',' };
                else if (headerLine.Contains(';')) delimiter = new[] { ';' };
            }

            var headers = headerLine.Split(delimiter, StringSplitOptions.None)
                .Select((h, i) => new { Index = i, Name = h.Trim() })
                .ToList();

            var knownHeader = headers.Any(h =>
                h.Name.Contains("Sample", StringComparison.OrdinalIgnoreCase) ||
                h.Name.Contains("File", StringComparison.OrdinalIgnoreCase) ||
                h.Name.Contains("Method", StringComparison.OrdinalIgnoreCase));

            if (!knownHeader)
                return null;

            int ColIndex(params string[] candidates)
            {
                foreach (var candidate in candidates)
                {
                    var norm = candidate.Replace(" ", "").ToLowerInvariant();
                    var hit = headers.FirstOrDefault(h =>
                        h.Name.Replace(" ", "").Equals(norm, StringComparison.OrdinalIgnoreCase) ||
                        h.Name.Equals(candidate, StringComparison.OrdinalIgnoreCase));
                    if (hit != null) return hit.Index;
                }
                return -1;
            }

            var sampleNameIdx = ColIndex("Sample Name", "SampleName", "Sample ID", "SampleID", "Sample");
            var positionIdx = ColIndex("Position", "PositionNo", "Position No");
            var typeIdx = ColIndex("Sample Type", "SampleType", "Type");
            var methodIdx = ColIndex("Inst Method", "InstrumentMethod", "Instrument Method", "Method", "MethodName");
            var polarityIdx = ColIndex("Polarity", "Ion Mode", "IonMode");
            var vialIdx = ColIndex("Vial", "VialPosition", "Vial Position");
            var fileIdx = ColIndex("File Name", "Filename", "Raw File", "RawFileName");
            var runtimeIdx = ColIndex("Runtime", "Run Time", "RunTime");

            if (sampleNameIdx < 0)
                return null;

            var samples = new List<SampleInfo>();
            for (var i = 1; i < lines.Count; i++)
            {
                var cols = lines[i].Split(delimiter, StringSplitOptions.None)
                    .Select(c => c.Trim())
                    .ToArray();
                if (cols.Length <= sampleNameIdx) continue;

                var sampleName = cols[sampleNameIdx];
                if (string.IsNullOrWhiteSpace(sampleName)) continue;

                var position = positionIdx >= 0 && cols.Length > positionIdx && int.TryParse(cols[positionIdx], out var p) ? p : samples.Count + 1;
                var sampleType = typeIdx >= 0 && cols.Length > typeIdx ? cols[typeIdx] : "Unknown";
                var methodName = methodIdx >= 0 && cols.Length > methodIdx ? cols[methodIdx] : null;
                var polarity = polarityIdx >= 0 && cols.Length > polarityIdx ? cols[polarityIdx] : "positive";
                var vial = vialIdx >= 0 && cols.Length > vialIdx ? cols[vialIdx] : null;
                var rawFile = fileIdx >= 0 && cols.Length > fileIdx ? cols[fileIdx] : null;
                int? runtime = runtimeIdx >= 0 && cols.Length > runtimeIdx && int.TryParse(cols[runtimeIdx], out var r) ? r : null;

                samples.Add(new SampleInfo(
                    sampleName,
                    position,
                    sampleName,
                    sampleType,
                    methodName,
                    string.IsNullOrWhiteSpace(polarity) ? "positive" : polarity.ToLowerInvariant(),
                    vial,
                    rawFile,
                    runtime));
            }

            return samples.Count > 0 ? samples : null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to parse sequence file {Path}.", path);
            return null;
        }
    }

    private void ApplyAcquisitionContext(IDictionary<string, string> info)
    {
        var snapshot = ParseAcquisitionOpening(info);
        _currentSequenceId = snapshot.ExternalSequenceId;
        _currentSequenceName = snapshot.SequenceName;
        if (snapshot.Samples.Count > 0)
        {
            var s = snapshot.Samples[0];
            _currentSampleId = s.ExternalSampleId;
            _currentSampleName = s.SampleName;
            _currentSamplePolarity = string.IsNullOrWhiteSpace(s.Polarity) ? "positive" : s.Polarity;
        }
    }

    private SequenceSnapshot ParseAcquisitionOpening(IDictionary<string, string> info)
    {
        info.TryGetValue("Sequence", out var sequence);
        info.TryGetValue("SequenceName", out var sequenceName);
        info.TryGetValue("Sample", out var sample);
        info.TryGetValue("SampleName", out var sampleName);
        info.TryGetValue("Position", out var positionText);
        info.TryGetValue("Method", out var method);
        info.TryGetValue("Polarity", out var polarity);
        info.TryGetValue("Vial", out var vial);
        info.TryGetValue("RawFile", out var rawFile);

        if (string.IsNullOrWhiteSpace(sequence)) sequence = info.Keys.FirstOrDefault(k => k.Contains("Sequence", StringComparison.OrdinalIgnoreCase)) is { } key ? info[key] : "SEQ-HELIOS-001";
        if (string.IsNullOrWhiteSpace(sequenceName)) sequenceName = sequence;
        if (string.IsNullOrWhiteSpace(sample)) sample = info.Keys.FirstOrDefault(k => k.Contains("Sample", StringComparison.OrdinalIgnoreCase)) is { } key ? info[key] : "SMP-001";
        if (string.IsNullOrWhiteSpace(sampleName)) sampleName = sample;

        return new SequenceSnapshot(
            sequence,
            sequenceName,
            new List<SampleInfo>
            {
                new(
                    sample,
                    int.TryParse(positionText, out var pos) ? pos : 1,
                    sampleName,
                    "Unknown",
                    method,
                    string.IsNullOrWhiteSpace(polarity) ? "positive" : polarity.ToLowerInvariant(),
                    vial,
                    rawFile,
                    null)
            });
    }

    private SequenceSnapshot DefaultSequenceSnapshot() =>
        new("SEQ-HELIOS-001", "Helios Sequence", new List<SampleInfo>());

    private ScanEvent? ConvertScan(IMsScan scan)
    {
        if (scan is not ISpectrum spectrum) return null;

        var header = scan.Header;
        var scanNumber = GetHeaderInt(header, "ScanNumber", "scanNumber", "Scan");
        var rt = GetHeaderDouble(header, "StartTime", "startTime", "RetentionTime") / 60.0;
        if (double.IsNaN(rt) || rt <= 0) rt = 0;
        var msOrder = GetHeaderInt(header, "MsOrder", "MSOrder", "msOrder");
        var polarity = NormalizePolarity(GetHeaderString(header, "Polarity", "polarity", "IonMode") ?? _currentSamplePolarity);
        var scanType = GetHeaderString(header, "ScanType", "scanType", "Filter") ?? "Full";
        var tic = GetHeaderDouble(header, "TIC", "TotalIonCurrent", "totalIonCurrent");
        var basePeakMz = GetHeaderDouble(header, "BasePeakMz", "BasePeakMass", "basePeakMz");
        var basePeakIntensity = GetHeaderDouble(header, "BasePeakIntensity", "basePeakIntensity");
        var lowMz = GetHeaderDouble(header, "LowMass", "lowMass", "LowMz");
        var highMz = GetHeaderDouble(header, "HighMass", "highMass", "HighMz");

        var mz = new List<double>();
        var intensities = new List<double>();
        foreach (var centroid in spectrum.Centroids.OrderBy(c => c.Mz))
        {
            mz.Add(centroid.Mz);
            intensities.Add(centroid.Intensity);
        }

        if (!mz.Any())
        {
            _logger.LogTrace("Scan {ScanNumber} has no centroids.", scanNumber);
            return null;
        }

        return new ScanEvent(
            Guid.NewGuid(),
            _currentSequenceId,
            _currentSampleId,
            scanNumber,
            Math.Round(rt, 3),
            msOrder,
            polarity,
            scanType,
            double.IsNaN(tic) ? intensities.Sum() : tic,
            double.IsNaN(basePeakMz) ? null : basePeakMz,
            double.IsNaN(basePeakIntensity) ? null : basePeakIntensity,
            double.IsNaN(lowMz) ? mz.Min() : lowMz,
            double.IsNaN(highMz) ? mz.Max() : highMz,
            mz,
            intensities);
    }

    private void ExtractTelemetry(IMsScan scan)
    {
        ExtractFromInformationSource(scan.StatusLog, "StatusLog");
        ExtractFromInformationSource(scan.Trailer, "Trailer");
    }

    private void ExtractFromInformationSource(IInformationSourceAccess? source, string sourceName)
    {
        if (source?.Available != true || source?.Valid != true) return;

        foreach (var key in source.ItemNames)
        {
            if (!source.TryGetValue(key, out var valueText) || string.IsNullOrWhiteSpace(valueText)) continue;
            if (TryParseDouble(valueText, out var value))
            {
                var metricName = MapTelemetryName(key, sourceName);
                _latestTelemetry[metricName] = value;
                _telemetryChannel.Writer.TryWrite(new TelemetryEvent(DateTime.UtcNow, metricName, value, null));
            }
        }
    }

    private static string MapTelemetryName(string key, string source)
    {
        var lower = key.ToLowerInvariant();
        return lower switch
        {
            var s when s.Contains("spray") && s.Contains("voltage") => "SprayVoltage",
            var s when s.Contains("sheath") => "SheathGas",
            var s when s.Contains("aux") => "AuxGas",
            var s when s.Contains("sweep") => "SweepGas",
            var s when s.Contains("capillary") && (s.Contains("temp") || s.Contains("temperature")) => "CapillaryTemperature",
            var s when s.Contains("s-lens") || s.Contains("slens") || s.Contains("s lens") => "SLensRFLevel",
            var s when s.Contains("pressure") && s.Contains("ms") => "MsPressure",
            var s when s.Contains("detector") && s.Contains("count") => "DetectorCounts",
            _ => $"{source}.{key}"
        };
    }

    private static T? GetProperty<T>(object? target, string name)
    {
        if (target is null) return default;
        try
        {
            var prop = target.GetType().GetProperty(name, BindingFlags.Public | BindingFlags.Instance);
            if (prop is null) return default;
            var value = prop.GetValue(target);
            if (value is null) return default;
            return (T?)Convert.ChangeType(value, typeof(T));
        }
        catch
        {
            return default;
        }
    }

    private static int GetHeaderInt(IDictionary<string, string> header, params string[] keys)
    {
        foreach (var key in keys)
        {
            if (header.TryGetValue(key, out var value) && int.TryParse(value, NumberStyles.Any, CultureInfo.InvariantCulture, out var result))
                return result;
        }
        return 0;
    }

    private static double GetHeaderDouble(IDictionary<string, string> header, params string[] keys)
    {
        foreach (var key in keys)
        {
            if (header.TryGetValue(key, out var value) && TryParseDouble(value, out var result))
                return result;
        }
        return double.NaN;
    }

    private static string? GetHeaderString(IDictionary<string, string> header, params string[] keys)
    {
        foreach (var key in keys)
        {
            if (header.TryGetValue(key, out var value) && !string.IsNullOrWhiteSpace(value))
                return value;
        }
        return null;
    }

    private static bool TryParseDouble(string text, out double value)
    {
        return double.TryParse(text.Replace(',', ' '), NumberStyles.Float | NumberStyles.AllowThousands, CultureInfo.InvariantCulture, out value);
    }

    private static string NormalizePolarity(string? value)
    {
        if (string.IsNullOrWhiteSpace(value)) return "unknown";
        var v = value.ToLowerInvariant();
        if (v.Contains("pos") || v.Contains("+")) return "positive";
        if (v.Contains("neg") || v.Contains("-")) return "negative";
        return v;
    }

    private sealed class ActionDisposable : IDisposable
    {
        private readonly Action _action;
        public ActionDisposable(Action action) => _action = action;
        public void Dispose() => _action();
    }
}
