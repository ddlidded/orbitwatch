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
        var backendUrl = config.GetValue<string>("Agent:BackendUrl");
        if (string.IsNullOrWhiteSpace(backendUrl) || !Uri.TryCreate(backendUrl, UriKind.Absolute, out var baseAddress))
        {
            throw new InvalidOperationException($"Agent:BackendUrl is missing or invalid: '{backendUrl}'. Set it to your OrbitWatch backend URL (e.g. https://orbitwatch.yourdomain.com).");
        }
        _httpClient.BaseAddress = baseAddress;
    }

    public async Task<AgentRegisterResponse?> RegisterAsync(string bootstrapToken, AgentRegisterPayload payload, CancellationToken cancellationToken = default)
    {
        try
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
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Agent registration request failed; will retry.");
            return null;
        }
    }

    public async Task<bool> SendAsync(string agentToken, MessageEnvelope envelope, CancellationToken cancellationToken = default)
    {
        try
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
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to send message {MessageId}; will retry.", envelope.MessageId);
            return false;
        }
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
