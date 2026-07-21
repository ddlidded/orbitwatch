using OrbitWatchAgent;
using OrbitWatchAgent.Models;
using OrbitWatchAgent.Services;
using Serilog;

var builder = Host.CreateApplicationBuilder(args);
builder.Services.AddWindowsService(options => options.ServiceName = "OrbitWatchAgent");
builder.Services.AddHostedService<Worker>();
builder.Services.AddSingleton<IInstrumentDataSource>(provider =>
{
    var config = provider.GetRequiredService<IConfiguration>();
    var loggerFactory = provider.GetRequiredService<ILoggerFactory>();
    var mode = config.GetValue<string>("Agent:Mode");
    if (string.Equals(mode, "helios", StringComparison.OrdinalIgnoreCase))
    {
        return new HeliosInstrumentDataSource(loggerFactory.CreateLogger<HeliosInstrumentDataSource>(), config);
    }
    return new ReplayInstrumentDataSource(loggerFactory.CreateLogger<ReplayInstrumentDataSource>(), config);
});
builder.Services.AddSingleton<DurableMessageQueue>();
builder.Services.AddHttpClient<MessageEnvelopeSender>();
builder.Services.AddSingleton<MessageEnvelopeSender>();

// Ensure content root and logs are next to the executable so the service/agent behaves the same
// whether it is started from a console or the Windows Service Control Manager.
builder.Environment.ContentRootPath = AppContext.BaseDirectory;

var backendUrl = builder.Configuration.GetValue<string>("Agent:BackendUrl");
if (string.IsNullOrWhiteSpace(backendUrl) || !Uri.TryCreate(backendUrl, UriKind.Absolute, out _))
{
    var message = $"Agent:BackendUrl is missing or invalid: '{backendUrl}'. Set it to your OrbitWatch backend URL (e.g. https://orbitwatch.yourdomain.com) in appsettings.json or appsettings.Production.json.";
    Console.WriteLine(message);
    if (Environment.UserInteractive)
    {
        Console.WriteLine("Press any key to exit.");
        try { Console.ReadKey(true); } catch { }
    }
    Environment.Exit(1);
    return;
}

var logDirectory = Path.Combine(AppContext.BaseDirectory, "logs");
Directory.CreateDirectory(logDirectory);
var logPath = Path.Combine(logDirectory, "orbitwatch-agent-.log");

Log.Logger = new LoggerConfiguration()
    .MinimumLevel.Information()
    .WriteTo.Console()
    .WriteTo.File(logPath, rollingInterval: RollingInterval.Day)
    .CreateLogger();

builder.Logging.AddSerilog(Log.Logger);

var host = builder.Build();

try
{
    host.Run();
}
catch (Exception ex)
{
    Log.Logger.Fatal(ex, "Agent terminated unexpectedly.");
    if (Environment.UserInteractive)
    {
        Console.WriteLine($"Fatal error: {ex.Message}");
        Console.WriteLine($"See {logPath} for details.");
        Console.WriteLine("Press any key to exit.");
        try { Console.ReadKey(true); } catch { }
    }
    Environment.Exit(1);
}
