# IDS701 Scale Integration — Windows Client Package

This directory is independent of Flask and the application database. The bridge receives IDS701
ASCII frames, calculates Software Tare in memory, and exposes local state on loopback only. It
never sends bytes to a scale and never writes a weighing transaction.

## Protocol and serial settings

The parser accepts CR/LF-terminated `ST`, `US`, and `OL` frames in Gross (`GS`) or Net (`NT`)
mode. Weight uses `Decimal`; malformed input returns `NOT_DECODED` and never becomes zero. The
approved Windows connection is FTDI `0403:6001`, default `COM3`, `9600/8N1`, and no flow control.
Install the isolated runtime dependency with:

```powershell
py -m venv .venv-scale
.venv-scale\Scripts\python -m pip install -r scale_bridge\requirements.txt
```

List matching devices without changing them:

```powershell
powershell -ExecutionPolicy Bypass -File scale_bridge\windows\list_ftdi_devices.ps1
```

Local configuration supplies a manual `scale_code`, optional USB serial number, workstation,
and explicit COM port. If the adapter reports a unique USB serial, discovery follows it when its
COM number changes. Without a unique serial, the configured Scale Code and COM port remain the
operator-controlled identity; the software does not invent hardware identity.

## Loopback API

`create_server()` always binds `127.0.0.1`. It requires explicit allowed Origins and provides:

- `GET /health`
- `GET /status` and `GET /reading`
- `POST /tare/capture` and `POST /tare/clear`
- `POST /context`

State-changing calls require an allowed `Origin`. CORS never uses `*`. There is no endpoint for
serial output, Zero, Hardware Tare, Calibration, Reset, Print, or device configuration.

Development-mode startup remains available from the repository root:

```powershell
.venv-scale\Scripts\python -m scale_bridge `
  --config C:\ProgramData\SCT\ScaleBridge\config.json
```

The packaged service discovers FTDI `0403:6001` devices automatically. One matching device is
selected automatically; multiple matches remain safely disconnected until an administrator stores
the preferred USB serial through diagnostics. Discovery runs again after every reconnect.

See [Browser Integration Contract](api-contract.md) and [Windows Package](windows-package.md).

Controlled states exposed by the bridge include `PORT_MISSING`, `PORT_BUSY`, `DISCONNECTED`,
`NOT_DECODED`, `OVERLOAD`, and reconnect-session changes.

## macOS simulator

The simulator writes genuine IDS701 byte frames to a pseudo-terminal, not a Windows COM device.
The parser and read path are the same; only OS device discovery/opening differs.

From the repository root:

```bash
.venv/bin/python -m scale_bridge.simulator.cli --interval 0.5 \
  --tare-weight 0.80 --gross-weight 3.82
```

Use the printed `/dev/ttys...` device as the explicit simulator port in a local bridge harness.
The repeating demonstration represents empty scale, empty container, material added, unstable
reading (Save blocked), then stable reading (Save eligible after Software Tare). Changing Material,
PO, Formula Item, Station, Scale, or reconnecting clears Tare. Tests also cover negative, overload,
Net, malformed, partial, combined, disconnect, and reconnect scenarios.

Run prototype tests without hardware or external network access:

```bash
.venv/bin/pytest -q scale_bridge/tests
```
