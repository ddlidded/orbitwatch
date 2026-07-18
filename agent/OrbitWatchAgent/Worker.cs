using System.Collections.Concurrent;
using System.Text.Json;
using OrbitWatchAgent.Models;
using OrbitWatchAgent.Services;

namespace OrbitWatchAgent;

public sealed class Worker : BackgroundService
{
    private readonly ILogger<Worker> _logger;
    private readonly IInstrumentDataSource _instrument;
    private readonly DurableMessageQueue _queue;
    private readonly MessageEnvelopeSender _sender;
    private readonly IConfiguration _config;
    private long _sequenceNumber;
    private string _agentToken = "";
    private Guid _agentId;
    private Guid _instrumentId;

    public Worker(ILogger<Worker> logger, IInstrumentDataSource instrument, DurableMessageQueue queue, MessageEnvelopeSender sender, IConfiguration config)
    {
        _logger = logger;
        _instrument = instrument;
        _queue = queue;
        _sender = sender;
        _config = config;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("OrbitWatch agent starting...");

        var identity = await _instrument.GetInstrumentIdentityAsync(stoppingToken);
        var capabilities = new Dictionary<string, bool> { ["scan"] = true, ["telemetry"] = true, ["rawfile"] = true };
        var hostname = Environment.MachineName;
        var agentVersion = "0.0.1";

        var registerPayload = new AgentRegisterPayload(hostname, agentVersion, identity.SerialNumber, identity.Name, identity.Model, identity.ApiVersion, identity.TuneVersion, identity.IapiVersion, capabilities);
        var bootstrapToken = _config.GetValue<string>("Agent:BootstrapToken") ?? "";

        AgentRegisterResponse? registration = null;
        while (registration is null && !stoppingToken.IsCancellationRequested)
        {
            registration = await _sender.RegisterAsync(bootstrapToken, registerPayload, stoppingToken);
            if (registration is null)
            {
                _logger.LogError("Agent registration failed. Retrying in 30s.");
                await Task.Delay(TimeSpan.FromSeconds(30), stoppingToken);
            }
        }

        if (registration is null)
            return;

        _agentToken = registration.Token;
        _agentId = registration.AgentId;
        _instrumentId = registration.InstrumentId;

        // Start outbox sender loop.
        _ = Task.Run(() => RunOutboxSender(stoppingToken), stoppingToken);

        // Start telemetry stream in the background so instrument health metrics are sent concurrently with scans.
        var telemetryTask = Task.Run(() => RunTelemetryAsync(stoppingToken), stoppingToken);

        var sequence = await _instrument.GetSequenceSnapshotAsync(stoppingToken);
        await EnqueueAsync("sequence.started", new Dictionary<string, object?>
        {
            ["external_sequence_id"] = sequence.ExternalSequenceId,
            ["sequence_name"] = sequence.SequenceName,
            ["started_at"] = DateTime.UtcNow.ToString("O"),
            ["samples"] = JsonSerializer.Deserialize<List<Dictionary<string, object?>>>(
                JsonSerializer.Serialize(sequence.Samples, new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower }))
        }, stoppingToken);

        foreach (var sample in sequence.Samples)
        {
            await EnqueueAsync("sample.started", new Dictionary<string, object?>
            {
                ["external_sequence_id"] = sequence.ExternalSequenceId,
                ["external_sample_id"] = sample.ExternalSampleId,
                ["started_at"] = DateTime.UtcNow.ToString("O")
            }, stoppingToken);

            await foreach (var scan in _instrument.StreamScansAsync(sample.ExternalSampleId, stoppingToken).WithCancellation(stoppingToken))
            {
                await EnqueueAsync("scan", new Dictionary<string, object?>
                {
                    ["external_sequence_id"] = scan.ExternalSequenceId,
                    ["external_sample_id"] = scan.ExternalSampleId,
                    ["scan_number"] = scan.ScanNumber,
                    ["retention_time_minutes"] = scan.RetentionTimeMinutes,
                    ["ms_order"] = scan.MsOrder,
                    ["polarity"] = scan.Polarity,
                    ["scan_type"] = scan.ScanType,
                    ["tic"] = scan.Tic,
                    ["base_peak_mz"] = scan.BasePeakMz,
                    ["base_peak_intensity"] = scan.BasePeakIntensity,
                    ["low_mz"] = scan.LowMz,
                    ["high_mz"] = scan.HighMz,
                    ["mz_array"] = scan.MzArray,
                    ["intensity_array"] = scan.IntensityArray
                }, stoppingToken);
            }

            await EnqueueAsync("sample.completed", new Dictionary<string, object?>
            {
                ["external_sequence_id"] = sequence.ExternalSequenceId,
                ["external_sample_id"] = sample.ExternalSampleId,
                ["completed_at"] = DateTime.UtcNow.ToString("O")
            }, stoppingToken);
        }

        await telemetryTask;
    }

    private async Task RunTelemetryAsync(CancellationToken cancellationToken)
    {
        try
        {
            await foreach (var telemetry in _instrument.StreamTelemetryAsync(cancellationToken).WithCancellation(cancellationToken))
            {
                await EnqueueAsync("telemetry.batch", new Dictionary<string, object?>
                {
                    ["metrics"] = new List<Dictionary<string, object?>>
                    {
                        new() { ["metric_name"] = telemetry.MetricName, ["metric_value"] = telemetry.Value, ["unit"] = telemetry.Unit, ["recorded_at"] = telemetry.Timestamp.ToString("O") }
                    }
                }, cancellationToken);
            }
        }
        catch (OperationCanceledException)
        {
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Telemetry stream error.");
        }
    }

    private async Task EnqueueAsync(string type, Dictionary<string, object?> payload, CancellationToken cancellationToken)
    {
        var messageId = Guid.NewGuid();
        var envelope = new MessageEnvelope("1.0", messageId, _agentId, _instrumentId, Interlocked.Increment(ref _sequenceNumber), DateTime.UtcNow, type, payload);
        await _queue.EnqueueAsync(messageId.ToString(), envelope, cancellationToken);
    }

    private async Task RunOutboxSender(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                var messages = await _queue.GetUnsentAsync(50, cancellationToken);
                foreach (var msg in messages)
                {
                    var envelope = JsonSerializer.Deserialize<MessageEnvelope>(msg.Payload, DurableMessageQueue.JsonOptions);
                    if (envelope is null)
                    {
                        await _queue.MarkSentAsync(msg.Id, cancellationToken);
                        continue;
                    }
                    if (await _sender.SendAsync(_agentToken, envelope, cancellationToken))
                    {
                        await _queue.MarkSentAsync(msg.Id, cancellationToken);
                    }
                    else
                    {
                        await _queue.IncrementRetryAsync(msg.Id, cancellationToken);
                    }
                }
                await Task.Delay(TimeSpan.FromSeconds(1), cancellationToken);
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Outbox sender error.");
                await Task.Delay(TimeSpan.FromSeconds(5), cancellationToken);
            }
        }
    }
}
