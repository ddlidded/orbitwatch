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

Log.Logger = new LoggerConfiguration()
    .MinimumLevel.Information()
    .WriteTo.Console()
    .WriteTo.File("logs/orbitwatch-agent-.log", rollingInterval: RollingInterval.Day)
    .CreateLogger();

builder.Logging.AddSerilog(Log.Logger);

var host = builder.Build();
host.Run();
