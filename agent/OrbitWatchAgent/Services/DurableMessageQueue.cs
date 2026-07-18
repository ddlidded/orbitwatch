using Microsoft.Data.Sqlite;
using System.Text.Json;
using OrbitWatchAgent.Models;

namespace OrbitWatchAgent.Services;

public sealed class DurableMessageQueue : IDisposable
{
    internal static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = false,
    };

    private readonly string _connectionString;
    private readonly ILogger<DurableMessageQueue> _logger;
    private readonly SemaphoreSlim _lock = new(1, 1);

    public DurableMessageQueue(IConfiguration config, ILogger<DurableMessageQueue> logger)
    {
        _logger = logger;
        var path = config.GetValue<string>("Agent:Queue:Path") ?? "data/agent-queue.db";
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        _connectionString = $"Data Source={path}";
        Initialize();
    }

    private void Initialize()
    {
        using var conn = new SqliteConnection(_connectionString);
        conn.Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            CREATE TABLE IF NOT EXISTS outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                sent_at TEXT,
                retry_count INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_outbox_sent ON outbox(sent_at);
        ";
        cmd.ExecuteNonQuery();
    }

    public async Task EnqueueAsync(string messageId, MessageEnvelope envelope, CancellationToken cancellationToken = default)
    {
        await _lock.WaitAsync(cancellationToken);
        try
        {
            using var conn = new SqliteConnection(_connectionString);
            await conn.OpenAsync(cancellationToken);
            using var cmd = conn.CreateCommand();
            cmd.CommandText = "INSERT INTO outbox (message_id, payload, created_at) VALUES (@mid, @payload, @createdAt)";
            cmd.Parameters.AddWithValue("@mid", messageId);
            cmd.Parameters.AddWithValue("@payload", JsonSerializer.Serialize(envelope, JsonOptions));
            cmd.Parameters.AddWithValue("@createdAt", DateTime.UtcNow.ToString("O"));
            await cmd.ExecuteNonQueryAsync(cancellationToken);
        }
        finally
        {
            _lock.Release();
        }
    }

    public async Task<List<OutboxMessage>> GetUnsentAsync(int limit, CancellationToken cancellationToken = default)
    {
        var messages = new List<OutboxMessage>();
        using var conn = new SqliteConnection(_connectionString);
        await conn.OpenAsync(cancellationToken);
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT id, message_id, payload, retry_count FROM outbox WHERE sent_at IS NULL ORDER BY id LIMIT @limit";
        cmd.Parameters.AddWithValue("@limit", limit);
        using var reader = await cmd.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            messages.Add(new OutboxMessage(
                reader.GetInt64(0),
                reader.GetString(1),
                reader.GetString(2),
                reader.GetInt32(3)
            ));
        }
        return messages;
    }

    public async Task MarkSentAsync(long id, CancellationToken cancellationToken = default)
    {
        using var conn = new SqliteConnection(_connectionString);
        await conn.OpenAsync(cancellationToken);
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "UPDATE outbox SET sent_at = @sentAt WHERE id = @id";
        cmd.Parameters.AddWithValue("@sentAt", DateTime.UtcNow.ToString("O"));
        cmd.Parameters.AddWithValue("@id", id);
        await cmd.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task IncrementRetryAsync(long id, CancellationToken cancellationToken = default)
    {
        using var conn = new SqliteConnection(_connectionString);
        await conn.OpenAsync(cancellationToken);
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "UPDATE outbox SET retry_count = retry_count + 1 WHERE id = @id";
        cmd.Parameters.AddWithValue("@id", id);
        await cmd.ExecuteNonQueryAsync(cancellationToken);
    }

    public void Dispose()
    {
        _lock.Dispose();
    }
}

public record OutboxMessage(long Id, string MessageId, string Payload, int RetryCount);
