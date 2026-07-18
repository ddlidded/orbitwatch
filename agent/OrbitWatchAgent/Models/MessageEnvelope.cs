namespace OrbitWatchAgent.Models;

public record MessageEnvelope(
    string SchemaVersion,
    Guid MessageId,
    Guid AgentId,
    Guid InstrumentId,
    long SequenceNumber,
    DateTime SentAt,
    string Type,
    Dictionary<string, object?> Payload
);
