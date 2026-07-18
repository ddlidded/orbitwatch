# Xcalibur / Thermo IAPI Integration

The OrbitWatch Windows agent can read the active Xcalibur sequence and real-time
MS scan data from a Thermo Exploris 480 using the Thermo Instrument Access
Framework (IAPI) .NET Standard reference assemblies.

## How sequence data is obtained (read-only)

The agent never modifies the Xcalibur sequence, method, Tune parameters, or
instrument state. It only reads:

1. `IState.SequenceFileName` and `IState.SequenceFileIndex` from the active
   acquisition state.
2. The sequence file referenced by `SequenceFileName` is parsed as a tab/comma
   delimited sample list when possible.
3. The `AcquisitionStreamOpening` event's `StartingInformation` dictionary is
   used as a fallback to identify the current sample, method, polarity, and raw
   file name as each acquisition begins.

## Agent configuration

Set the agent mode to `helios` in `appsettings.Production.json` on the
instrument PC:

```jsonc
{
  "Agent": {
    "Mode": "helios",
    "ServerUrl": "https://orbitwatch.example.com/api/v1/agents",
    "BootstrapToken": "<one-time registration token from backend>",
    "Instrument": {
      "Serial": "<instrument serial number>",
      "Name": "Exploris 480",
      "Model": "Orbitrap Exploris 480"
    }
  }
}
```

The agent discovers the IAPI implementation from the registry key
`SOFTWARE\Thermo Exploris` and the `DataSystem.xml` file in the Thermo
application-data folder. The reference DLLs are vendored in
`agent/OrbitWatchAgent/lib/`, but the full IAPI/Tune runtime must be installed
on the instrument PC.

## Limitations

- Native `.sld` binary sequence files cannot be parsed reliably without the
  Xcalibur COM objects; in that case the agent reports the active row from
  `IState.SequenceFileIndex` and the `AcquisitionStreamOpening` metadata.
- Scan centroids are read in real time; the agent does not read or write raw
  files.
