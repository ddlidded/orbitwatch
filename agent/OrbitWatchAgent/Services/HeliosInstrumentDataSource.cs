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

    public HeliosInstrumentDataSource(ILogger<HeliosInstrumentDataSource> logger, IConfiguration config)
    {
        _logger = logger;
        _config = config;
    }

    public Task<InstrumentIdentity> GetInstrumentIdentityAsync(CancellationToken cancellationToken = default)
    {
        EnsureConnected();
        var name = _config.GetValue<string>("Agent:Instrument:Name");
        var serial = _config.GetValue<string>("Agent:Instrument:Serial");
        if (_instrument is not null)
        {
            try { name = _instrument.InstrumentName; } catch (Exception ex) { _logger.LogWarning(ex, "Unable to read instrument name"); }
            // Serial number is not exposed directly by IAPI; it must be configured or read from Tune via registry.
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
        var tcs = new TaskCompletionSource<SequenceSnapshot>(TaskCreationOptions.RunContinuationsAsynchronously);

        EventHandler<ExplorisAcquisitionOpeningEventArgs>? handler = null;
        handler = (sender, e) =>
        {
            var snapshot = ParseAcquisitionOpening(e.StartingInformation);
            tcs.TrySetResult(snapshot);
        };

        try
        {
            _instrument!.Control.Acquisition.AcquisitionStreamOpening += handler;
            using var registration = cancellationToken.Register(() => tcs.TrySetCanceled());

            // If acquisition is already open and StartingInformation is not available, fall back to configured defaults.
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

    public async IAsyncEnumerable<ScanEvent> StreamScansAsync([EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        EnsureConnected();
        var channel = Channel.CreateUnbounded<ScanEvent>();

        EventHandler<ExplorisMsScanEventArgs>? handler = null;
        handler = (sender, e) =>
        {
            try
            {
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

        _scanContainer.MsScanArrived += handler;
        _subscriptions.Add(new ActionDisposable(() => _scanContainer!.MsScanArrived -= handler));

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
        var rt = GetHeaderDouble(header, "StartTime", "startTime", "RetentionTime") / 60.0; // IAPI StartTime is usually seconds
        if (double.IsNaN(rt) || rt <= 0) rt = 0;
        var msOrder = GetHeaderInt(header, "MsOrder", "MSOrder", "msOrder");
        var polarity = NormalizePolarity(GetHeaderString(header, "Polarity", "polarity", "IonMode"));
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

        var sequence = _config.GetValue<string>("Agent:Sequence:ExternalId") ?? "SEQ-HELIOS-001";
        var sample = _config.GetValue<string>("Agent:Sample:ExternalId") ?? "SMP-001";

        return new ScanEvent(
            Guid.NewGuid(),
            sequence,
            sample,
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
