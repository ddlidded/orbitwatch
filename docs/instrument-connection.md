# Instrument Connection Guide

This document describes how to connect a Thermo Scientific Orbitrap Exploris 480 mass spectrometer to OrbitWatch.

## Summary

OrbitWatch uses a small Windows service (the OrbitWatch Agent) that runs **on the instrument PC**. The agent:

- Reads sequence and scan data through Thermo's official IAPI (or Helios, which wraps IAPI).
- Streams that data outbound to the OrbitWatch backend over HTTPS/WebSocket.
- **Never accepts inbound connections** from the internet.
- **Never modifies Xcalibur sequences, Tune parameters, acquisition state, or source settings**.

## Requirements

1. Thermo IAPI runtime installed on the instrument PC (the same runtime used by Helios).
2. The instrument is online, Tune is running, and the instrument serial number is visible in the registry.
3. Network connectivity from the instrument PC to the OrbitWatch backend.
4. A valid TLS certificate in production (the backend rejects unencrypted `Agent:BackendUrl` in production).

## GUI Flow (Recommended)

1. Log in to OrbitWatch as a `system_admin` or `instrument_admin`.
2. Go to **Management → Connect Instrument**.
3. Fill in the instrument name, serial number, model, and optional API/Tune/IAPI versions.
4. Click **Register Instrument**.
5. The page displays an agent token, agent ID, and instrument ID.
6. Copy the generated `appsettings` JSON snippet.
7. On the instrument PC:
   - Install the `OrbitWatchAgent` Windows Service.
   - Edit `appsettings.Production.json` and paste the snippet.
   - Set `Agent:Mode` to `helios` to use the real Thermo IAPI, or `replay` for local testing.
8. Start the service. The agent authenticates with the pre-generated token and begins streaming.
9. Return to OrbitWatch **Dashboard**; the instrument status card should show `online` and the active sequence.

## Manual Registration (Alternative)

If you prefer to register from the instrument PC directly, start the agent with an empty `Agent:AgentToken` and a configured `Agent:BootstrapToken` matching the backend's `AGENT_BOOTSTRAP_TOKEN`. The agent will call `POST /api/v1/agents/register` and receive a token automatically. In production, `AGENT_BOOTSTRAP_TOKEN` must be set.

## Troubleshooting

- **Registration fails / 401 or 403**: Verify the token, agent ID, and instrument ID in `appsettings` match the GUI output exactly. If using bootstrap registration, confirm `AGENT_BOOTSTRAP_TOKEN` is set on the backend and matches `Agent:BootstrapToken`.
- **No sequence data**: Verify Xcalibur is running a sequence and that the IAPI runtime has loaded. The agent reads sequence information in a read-only manner from `IState` and `AcquisitionStreamOpening` events.
- **Agent crashes on startup**: Check that the vendored `Thermo.API.*.NetStd` DLLs are present next to the agent executable and that the .NET 8 runtime is installed.
- **Firewall**: The agent only makes outbound HTTPS/WebSocket calls on port 443. No inbound ports are required.

## Security Notes

- Keep the agent token secret and rotate it if the instrument PC is reinstalled or compromised.
- The agent does not expose the Thermo API or instrument computer to the network. All communication is initiated outbound.
- Store agent tokens in the agent's configuration file, never in source control or the browser.
