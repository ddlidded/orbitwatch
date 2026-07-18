using System.Net.Http.Json;
using System.Text.Json;
using OrbitWatchAgent.Models;

namespace OrbitWatchAgent.Services;

public sealed class MessageEnvelopeSender
{
    private readonly HttpClient _httpClient;
    private readonly IConfiguration _config;
    private readonly ILogger<MessageEnvelopeSender> _logger;
    private static readonly JsonSerializerOptions EnvelopeOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = false,
    };
    private static readonly JsonSerializerOptions RegisterOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = false,
    };

    public MessageEnvelopeSender(HttpClient httpClient, IConfiguration config, ILogger<MessageEnvelopeSender> logger)
    {
        _httpClient = httpClient;
        _config = config;
        _logger = logger;
        _httpClient.BaseAddress = new Uri(config.GetValue<string>("Agent:BackendUrl") ?? "http://localhost:8000");
    }

    public async Task<AgentRegisterResponse?> RegisterAsync(string bootstrapToken, AgentRegisterPayload payload, CancellationToken cancellationToken = default)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, "/api/v1/agents/register")
        {
            Content = JsonContent.Create(payload, options: RegisterOptions)
        };
        request.Headers.Add("x-agent-token", bootstrapToken);
        var response = await _httpClient.SendAsync(request, cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            _logger.LogError("Registration failed: {Status} {Body}", response.StatusCode, await response.Content.ReadAsStringAsync(cancellationToken));
            return null;
        }
        _logger.LogInformation("Agent registered.");
        return await response.Content.ReadFromJsonAsync<AgentRegisterResponse>(new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower }, cancellationToken: cancellationToken);
    }

    public async Task<bool> SendAsync(string agentToken, MessageEnvelope envelope, CancellationToken cancellationToken = default)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, "/api/v1/agents/messages")
        {
            Content = JsonContent.Create(envelope, options: EnvelopeOptions)
        };
        request.Headers.Add("x-agent-token", agentToken);
        var response = await _httpClient.SendAsync(request, cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            _logger.LogWarning("Failed to send message {MessageId}: {Status} {Body}", envelope.MessageId, response.StatusCode, await response.Content.ReadAsStringAsync(cancellationToken));
            return false;
        }
        return true;
    }
}

public record AgentRegisterPayload(
    string Hostname,
    string AgentVersion,
    string InstrumentSerial,
    string InstrumentName,
    string Model,
    string? ApiVersion,
    string? TuneVersion,
    string? IapiVersion,
    Dictionary<string, bool> Capabilities
);

public record AgentRegisterResponse(Guid AgentId, Guid InstrumentId, string Token);
