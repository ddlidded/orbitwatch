namespace OrbitWatchAgent.Services;

public interface IInstrumentDataSource
{
    Task<InstrumentIdentity> GetInstrumentIdentityAsync(CancellationToken cancellationToken = default);
    Task<SequenceSnapshot> GetSequenceSnapshotAsync(CancellationToken cancellationToken = default);
    IAsyncEnumerable<ScanEvent> StreamScansAsync(string? externalSampleId = null, CancellationToken cancellationToken = default);
    IAsyncEnumerable<TelemetryEvent> StreamTelemetryAsync(CancellationToken cancellationToken = default);
}

public record InstrumentIdentity(string SerialNumber, string Name, string Model, string? ApiVersion, string? TuneVersion, string? IapiVersion);
public record SequenceSnapshot(string ExternalSequenceId, string SequenceName, List<SampleInfo> Samples);
public record SampleInfo(string ExternalSampleId, int Position, string SampleName, string? SampleType, string? MethodName, string? Polarity, string? VialPosition, string? RawFileName, int? ExpectedRuntimeSeconds);
public record ScanEvent(Guid MessageId, string ExternalSequenceId, string ExternalSampleId, int ScanNumber, double RetentionTimeMinutes, int MsOrder, string Polarity, string ScanType, double Tic, double? BasePeakMz, double? BasePeakIntensity, double? LowMz, double? HighMz, List<double> MzArray, List<double> IntensityArray);
public record TelemetryEvent(DateTime Timestamp, string MetricName, double Value, string? Unit);
