# M4-RESULT — Cloud device plane (read-only half)

**RESULT: PASS (read-only half).** The agent logs into Bambu Cloud, the signed
network plugin loads headless, and the device API is reachable — login state,
account-bound printer enumeration, selection/status plumbing. The **write half**
(`send` / live `status` / `camera` / push events) is **pending a printer bound to
the test account** — not yet exercised.

Milestone M4 from SPEC §10. Split into a read-only half (done, here) and a write
half (blocked on a bound printer — a hardware/account step for the human).

---

## Checks (latest run)

- PASS — setup / path (a) / path (b) (M0 marshalling)
- PASS — **M4: device plane asserts** (verify_m4.py)
- PASS — interpreter finalized cleanly

Diagnostics (headless run against a copy of the logged-in datadir, **with a real
printer bound** to the account):
```
device.available   = True          # signed network plugin loaded offscreen
is_logged_in       = True          # login PERSISTED to the datadir copy
user_id            = <redacted-user-id>
refresh()          -> 1            # fetched the account's bound-printer list
printers()         = [('<redacted-printer-serial>', 'p2s', online=True)]   # real P2S
select(...) + status() = {online:True, print_status:'', progress:0,
                          current_layer:0, total_layers:0, remaining_s:0}  # idle
```
(An earlier run with no printer bound correctly returned `printers()==[]` — the
enumeration is real, not a stub.)

## Two findings that de-risk the whole device plane

1. **The signed `bambu_networking` plugin loads under the headless (Xvfb) harness.**
   The from-source fork can download the genuine plugins (see below) and the
   NetworkAgent initializes offscreen — the cloud device plane is not GUI-bound.
2. **Login persists across restarts, headless.** The account session survives into
   a *copy* of the datadir and a fresh offscreen launch comes up logged in. The
   token is on disk (encrypted — not grep-able as plaintext). **Implication:** the
   deployment/MCP-bridge instance can reuse a logged-in datadir; no need to hold a
   live GUI session or script re-login. This was the main open risk for M4.

## Surface delivered (read-only, isolated in PyDevice.cpp)

```
app.device.available          -> bool         # network plugin loaded?
app.device.is_logged_in       -> bool
app.device.user_id            -> str | None
app.device.user_name          -> str | None
app.device.refresh()          -> int          # fetch bound-printer list from cloud
app.device.printers()         -> list[BoundPrinter]   # account-bound (+ local)
app.device.selected           -> BoundPrinter | None
app.device.select(dev_id)     -> None
app.device.status(wait=0.0)   -> dict | None  # live telemetry (wait>0 = establish it)
BoundPrinter.dev_id / name / online / connection_type
# status() dict: dev_id, online, connected, awaiting_push, print_status, stage,
#   progress, current_layer, total_layers, remaining_s, subtask_name,
#   bed_temp/bed_temp_target, nozzles[{current,target}], chamber_temp[/target],
#   hms[{level, code}]
```

All routed through the GUI's own `NetworkAgent` / `DeviceManager`
(`getAgent()`, `getDeviceManager()`), main-thread-guarded, and **null-safe**: if
the plugin isn't loaded or the cloud is unreachable, every accessor degrades to
`False`/`None`/`[]` rather than throwing — honoring the "Device strictly isolated,
a cloud outage degrades printing only" invariant. Handles are `dev_id` strings,
re-resolved per call (a stale handle can't dereference a freed `MachineObject`).

## Setup notes (how the login rig was stood up)

- **Networking plugin:** the fork (v02.08.00.50) *can* download Bambu's genuine
  signed plugins — clicking "install network plugin" fetched
  `libbambu_networking.so`, `libBambuSource.so`, `libagora_rtc_sdk.so`
  (camera/liveview), `liblive555.so` into `<datadir>/plugins/`. Loads at startup
  after a restart. The version-pin risk did **not** bite.
- **Interactive login rig (for the human):** Xvfb `:1` + fluxbox + x11vnc on
  `:5901`, BambuStudio under `dbus-run-session`, connected with a VNC client. Used
  once to log in; the headless tests then reuse the persisted session.

## The SSO limitation (important product constraint)

The **OSS Linux build could not complete Apple ID (third-party SSO) login** —
Chris's real account uses Apple ID, and the login webview couldn't finish the
Apple flow; there's also no way to add a password to an existing SSO account.
Workaround: a **password-based** test account (`<test-account-email>`, id `<redacted-user-id>`).
**This belongs in SPEC §5:** any end user on Apple/Google SSO can't use the cloud
device plane on this OSS build. Worth investigating whether SSO is fixable or is an
official-build-only capability.

## Update — a real printer is now bound (P2S)

A P2S (`<redacted-printer-serial>`) is bound to the test account, and `refresh()` +
`printers()` + `select()` + `status()` are verified against it live. Added
`device.refresh()` because being logged in isn't enough — `DeviceManager` only
knows the bound printers after it fetches them from the cloud
(`update_user_machine_list_info()` → `get_user_print_info`, then a deferred JSON
parse); `refresh()` triggers that and pumps the loop until the list populates.

## Live telemetry — DONE, verified against the real P2S

`status(wait>0)` establishes and reads live telemetry. Headless is never "studio
active" (the app-subscribe gate in `GUI_App`'s idle handler), so it force-calls
`agent->start_subscribe("app")`, `command_request_push_all(true)`, and pumps the
loop until `is_connecting()` clears (a full push arrived), then reads the rich
fields. Verified live off an idle P2S: `print_status='FINISH'`, bed 16 °C /
nozzle 19 °C / chamber 21 °C (real ambient), and it even surfaced a `serious`
HMS alert (`0500060000020070`). `refresh()` was also hardened to wait for the
server MQTT connection and re-issue the fetch (a fresh instance can race its own
login). Also learned: **changing the account password unbinds the printer** —
rebind after a credential change.

## Camera + send — implemented

```
app.device.camera_url(timeout=10)              -> str | None  # liveview stream URL
app.device.send(plate=None, dry_run=False, …)  -> dict        # dispatch a sliced plate
```

- **`camera_url()`** returns the liveview stream URL (`bambu:///tutk|agora|rtsp`).
  A decoded *frame* is a separate media-pipeline task (libBambuSource + ffmpeg —
  deferred). Establish the device connection first (`status(wait>0)`) before calling it.
- **`send()`** mirrors the GUI: `Plater::send_gcode` exports the sliced 3mf (+
  config 3mf), then `NetworkAgent::start_print(PrintParams, …)`. **`dry_run=True`
  does everything except the dispatch** (export + build params) — verified live:
  sliced fixture → `dispatched:False, ready:True, connection:'cloud'`, the
  gcode.3mf on disk. **`dry_run=False` is the real dispatch and MUST only run with
  explicit, per-print user approval** (hard rule). The real path runs `start_print`
  on a worker thread while pumping the main loop (mirrors the GUI's PrintJob).

## Headless modal auto-dismisser

Run offscreen, cloud/device ops can pop `MessageDialog`s (e.g.
`process_network_msg` emits informational messages) — a `ShowModal` with no human wedges the app.
A repeating `wxTimer` (heap-allocated — a static one doesn't register before the
wx app exists) ends any stray modal, firing even inside a nested `ShowModal` loop.
This is general
headless-robustness the deployment needs.

## Still deferred

- **Real print dispatch** (`send(dry_run=False)`) — coded, but only ever run with
  explicit per-print approval; not exercised.
- **Push status/progress events** with reconnect + exponential backoff
  (cadence-sensitive — push-first, `pushall` only on reconnect). Shared machinery
  with M5's event → MCP-notification path.
- **Decoded camera frame** — needs the AV pipeline (libBambuSource + ffmpeg).

## Environment

BambuStudio 02.08.00.50 · Python 3.14.4 · pybind11 3.0.1 · wxWidgets 3.1.5 · GCC
15.2.0 · Ubuntu 26.04 (KVM). Network plugins downloaded from Bambu Cloud. Branch
`feat/py-runtime-m4` off `feat/py-runtime-m3`.
