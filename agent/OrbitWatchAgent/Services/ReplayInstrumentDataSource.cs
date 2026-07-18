using System.Collections.Generic;
using System.Runtime.CompilerServices;
using System.Text.Json;

namespace OrbitWatchAgent.Services;

public sealed class ReplayInstrumentDataSource : IInstrumentDataSource
{
    private readonly ILogger<ReplayInstrumentDataSource> _logger;
    private readonly string _replayFile;
    private readonly InstrumentIdentity _identity;
    private readonly List<SequenceSnapshot> _sequences = new();

    public ReplayInstrumentDataSource(ILogger<ReplayInstrumentDataSource> logger, IConfiguration config)
    {
        _logger = logger;
        _replayFile = config.GetValue<string>("Agent:Replay:File") ?? "";
        _identity = new InstrumentIdentity(
            config.GetValue<string>("Agent:Instrument:Serial") ?? "IQLAAEGAAPFADBMK",
            config.GetValue<string>("Agent:Instrument:Name") ?? "Exploris 480 (Replay)",
            config.GetValue<string>("Agent:Instrument:Model") ?? "Orbitrap Exploris 480",
            config.GetValue<string>("Agent:Instrument:ApiVersion") ?? "3.8.0.57",
            config.GetValue<string>("Agent:Instrument:TuneVersion") ?? "3.4.0.3122",
            config.GetValue<string>("Agent:Instrument:IapiVersion") ?? "3.8.0.57"
        );
        LoadReplay();
    }

    private void LoadReplay()
    {
        if (string.IsNullOrWhiteSpace(_replayFile) || !File.Exists(_replayFile))
        {
            _sequences.Add(GenerateDefaultSequence());
            return;
        }
        try
        {
            var json = File.ReadAllText(_replayFile);
            var snapshot = JsonSerializer.Deserialize<SequenceSnapshot>(json, new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
            if (snapshot is not null)
                _sequences.Add(snapshot);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to load replay file; using default sequence.");
            _sequences.Add(GenerateDefaultSequence());
        }
    }

    private static SequenceSnapshot GenerateDefaultSequence() =>
        new("SEQ-REPLAY-001", "Replay QC Sequence", new List<SampleInfo>
        {
            new("SMP-001", 1, "QC-Replay-01", "QC", "HILIC-pos-neg", "positive", "A1", "QC_Replay_01.raw", 900)
        });

    public Task<InstrumentIdentity> GetInstrumentIdentityAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(_identity);

    public Task<SequenceSnapshot> GetSequenceSnapshotAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(_sequences.FirstOrDefault() ?? GenerateDefaultSequence());

    public async IAsyncEnumerable<ScanEvent> StreamScansAsync([EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        var sequence = _sequences.FirstOrDefault() ?? GenerateDefaultSequence();
        var sample = sequence.Samples.First();
        var rng = new Random(42);
        var compounds = new Dictionary<string, (double Mz, double Rt, double Intensity, double SigmaRt)>
        {
            ["SAM"] = (399.1448, 6.42, 2.8e6, 0.12),
            ["SAH"] = (385.1292, 5.88, 1.3e6, 0.10),
            ["Betaine"] = (118.0864, 4.80, 8.0e3, 0.08),
            ["Citrate"] = (191.0191, 7.19, 4.0e5, 0.14),
            ["Adenosine"] = (268.1030, 4.55, 1.0e5, 0.10),
        };

        for (int scanNumber = 1; scanNumber <= 300 && !cancellationToken.IsCancellationRequested; scanNumber++)
        {
            var rt = scanNumber * 0.05;
            var tic = 1.5e6 + rng.NextDouble() * 5e4;
            var peaks = new List<(double Mz, double Intensity)>();
            foreach (var (name, info) in compounds)
            {
                var intensity = info.Intensity * Math.Exp(-Math.Pow(rt - info.Rt, 2) / (2 * info.SigmaRt * info.SigmaRt));
                peaks.Add((info.Mz, intensity));
                tic += intensity;
            }

            var mzSet = new SortedSet<double>();
            for (double mz = 50.0; mz <= 500.0; mz += 0.1)
                mzSet.Add(Math.Round(mz, 1));
            foreach (var peak in peaks)
                mzSet.Add(peak.Mz);

            var mzArray = new List<double>();
            var intensityArray = new List<double>();
            foreach (var mz in mzSet)
            {
                var baseIntensity = rng.NextDouble() * 500 + 250;
                foreach (var peak in peaks)
                    baseIntensity += peak.Intensity * Math.Exp(-Math.Pow(mz - peak.Mz, 2) / (2 * 0.005 * 0.005));
                if (baseIntensity > 100)
                {
                    mzArray.Add(mz);
                    intensityArray.Add(baseIntensity);
                }
            }
            yield return new ScanEvent(
                Guid.NewGuid(),
                sequence.ExternalSequenceId,
                sample.ExternalSampleId,
                scanNumber,
                Math.Round(rt, 3),
                1,
                sample.Polarity ?? "positive",
                "Full",
                Math.Round(tic, 1),
                peaks.Count > 0 ? peaks[0].Mz : 0,
                peaks.Count > 0 ? peaks[0].Intensity : 0,
                mzArray.Count > 0 ? mzArray.Min() : 50,
                mzArray.Count > 0 ? mzArray.Max() : 500,
                mzArray,
                intensityArray
            );

            await Task.Delay(500, cancellationToken);
        }
    }

    public async IAsyncEnumerable<TelemetryEvent> StreamTelemetryAsync([EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            yield return new TelemetryEvent(DateTime.UtcNow, "SprayVoltage", 3.45, "kV");
            yield return new TelemetryEvent(DateTime.UtcNow, "CapillaryTemperature", 320, "C");
            yield return new TelemetryEvent(DateTime.UtcNow, "MsPressure", 2.1e-6, "mbar");
            await Task.Delay(TimeSpan.FromSeconds(5), cancellationToken);
        }
    }
}
