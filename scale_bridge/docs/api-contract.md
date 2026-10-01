# Browser Integration Contract

The installed service listens only on `http://127.0.0.1:<configured-port>`. A later Web UI may
call this API; Phase 2 does not change the Flask application.

## Origin policy

Browser `Origin` must exactly match an entry in machine configuration. Wildcards, suffix matching,
credentials, and cookies are not supported. `POST` and CORS preflight requests require an allowed
Origin. Responses echo only an exact allowed Origin and include `Vary: Origin`.

## Endpoints

- `GET /health`: process availability; does not imply scale connectivity.
- `GET /capabilities`: API version, receive-only guarantee, Software Tare support, and bilingual
  state definitions.
- `GET /status` and `GET /reading`: current connection, identity, frame, Gross, Tare, Actual,
  stability, freshness, save eligibility, and the non-secret persisted Workstation Code, Scale
  Code, preferred FTDI USB serial, and exact allowed Origins used by read-only diagnostics.
- `POST /context`: non-sensitive Material, PO, Formula Item, Station, and Scale context. Any change
  clears Software Tare.
- `POST /tare/capture`: captures the latest valid, fresh `ST,GS` kg value in memory.
- `POST /tare/clear`: clears in-memory Software Tare.

There are no serial output, device Tare, Zero, Calibration, Reset, Print, or configuration
endpoints. The API never writes an application weighing transaction.

## User states

The capability response provides Thai and English labels for:

- `BRIDGE_UNAVAILABLE`
- `DISCONNECTED`
- `MULTIPLE_SCALES`
- `READING_MISSING`
- `READING_UNSTABLE`
- `READING_STALE`
- `OVERLOAD`
- `TARE_MISSING`
- `READY`

The browser should distinguish `/health` success from `status.connected`. Connected becomes true
only after the service receives and decodes a valid IDS701 frame. Opening a COM port alone is not
proof of connectivity.
