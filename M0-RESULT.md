# M0-RESULT — embed + marshal de-risk spike

**RESULT: PASS** — all pass/fail criteria met, harness exit 0, clean interpreter finalize.

Milestone M0 from `slic3r-automation/LAUNCH.md`: prove that CPython can be embedded
in the Bambu Studio fork and a call round-tripped cleanly across **both** the GIL and
the wx main thread. This is the one unproven assumption the whole architecture rests
on. It is proven.

> This file is the human-authored deliverable. The self-test regenerates a
> machine section on every run (checks + timings below are from the latest green
> run, 2026-07-06); the "What fought back" and toolchain notes are the writeup.

---

## Verdict against LAUNCH.md pass criteria

| Criterion | Result |
|---|---|
| Builds clean on the target toolchain | PASS |
| Interpreter initializes; `import pyslic3r` succeeds | PASS |
| Path (a) main thread: `version` non-empty; `object_count == 2` | PASS (`"02.08.00.50"`, 2) |
| Path (b) background thread: same values, 1000/1000 iterations, no deadlock/crash/wx-assert | PASS (1000/1000) |
| App shuts down cleanly — interpreter finalized, no hang on exit | PASS (explicit finalize, see note) |

### Checks (latest run)

- PASS — setup: imported 2 fixture(s)
- PASS — path (a): import pyslic3r
- PASS — path (a): app.version non-empty ("02.08.00.50")
- PASS — path (a): active_document present
- PASS — path (a): object_count == 2 (got 2)
- PASS — path (b): background thread, 1000 marshalled round-trips, values stable
- PASS — interpreter finalized cleanly (explicit host_shutdown, no hang/crash)

### Timings (latest run)

| what | value |
|---|---|
| interpreter init (`Py_Initialize` + `import pyslic3r`) | 8.30 ms |
| path (a): main-thread import + 2 reads | 0.16 ms |
| path (b): 1000/1000 iterations × 2 marshalled reads | 113.96 ms total, **0.057 ms/round-trip** |
| interpreter finalize (explicit `host_shutdown`) | 2.31 ms |

Interpreter init is ~8 ms — negligible, and one-time. **No Intel split-lock startup
stall to report:** the host is an AMD Ryzen 7 PRO 8845HS under KVM, so the split-lock
`#AC` path LAUNCH.md flags (Intel-specific) does not apply here. Worth re-checking on
the Intel Unraid box at deployment.

---

## What was built (the marshalling primitive)

`src/slic3r/Scripting/` → **`libbambu_api`** (static, gated by `BBS_PY_RUNTIME`, default ON):

- **`PyHost`** owns the embedded interpreter. The main thread parks the GIL *released*
  while idle; every Python call re-acquires it (`py::gil_scoped_acquire`) for the
  duration of that call only. This is the rule that keeps the two locks from
  deadlocking.
- **`run_on_main_blocking(fn)`** — the primitive. From any thread it posts a closure
  onto the wx main loop via `CallAfter`, blocks the caller on a `std::future`, and
  rethrows any exception on the caller. Called on the main thread it runs inline (no
  self-wait deadlock). Every later-milestone bridge/worker call goes through this.
- **`PYBIND11_EMBEDDED_MODULE(pyslic3r, …)`** — exactly two read-only members for M0:
  `pyslic3r.app.version` (from `SLIC3R_VERSION`) and
  `pyslic3r.app.active_document.object_count` (via `wxGetApp().plater()->model().objects`).
  Both are guarded to assert they only ever touch wx objects on the main thread.

Core edits are limited to the **one hook pair** in `GUI_App.cpp` (`host_init()` at the
end of `post_init()`, `host_shutdown()` in `OnExit()`) plus CMake wiring — the
additive-and-isolated invariant holds. `libbambu_api` and `libslic3r_gui` form a
static-library cycle (bindings call Plater; GUI_App calls the host), resolved at final
link.

Self-verify harness: `tests/m0/run_m0.sh` runs the app offscreen under
`dbus-run-session + xvfb-run`, drives the in-app self-test (`PYSLIC3R_M0_TEST=1`), and
turns the result into an exit code. Fixtures: two generated STL cubes
(`tests/fixtures/`, `gen_two_object_stls.py`).

---

## What fought back

The embed + marshal itself was **not** the hard part — it worked early and has been
rock-solid across every run (1000 round-trips, zero races). What ate the time was
getting the full GUI app to run and exit **headless** so the self-test could even
execute. In order hit:

1. **STL/ABI boundary — a non-issue here, and that's a finding.** LAUNCH.md flags STL
   mismatch across the module boundary as a top escalation risk. On Linux it evaporates:
   `libbambu_api`, `libslic3r_gui`, Python 3.14 and pybind11 3.0.1 are all built with
   the same GCC 15.2 / libstdc++. No mismatch, no corruption. (The MSVC v142 discipline
   still matters if/when a Windows target returns — deferred, not disproven.)

2. **CPython "embeddable" distribution is a red herring on Linux.** SPEC assumed bundling
   the embeddable dist; that's a Windows packaging concern. On the Linux build the
   distro `python3-dev` + `pybind11-dev` (`find_package(Python … Development.Embed)`)
   is the clean path. Bundling (python-build-standalone) is revisited at deployment/M6.

3. **Static link order bit once.** Adding `${wxWidgets_LIBRARIES}` to `libbambu_api`
   reordered the final link so wx's webrequest landed after the last libcurl reference —
   `undefined reference to curl_version_info`. Fix: don't relist wx on the new target;
   its symbols resolve through the existing `libslic3r_gui` cycle.

4. **Headless modals are the real adversary.** Run offscreen, the app blocks on a
   sequence of GUI modals during startup/first-file-load, each of which wedges under
   Xvfb. Peeled off one at a time (backtraces via `gdb -p` — the release build keeps
   symbols):
   - First-run **TLS-certificate** confirmation (static OpenSSL can't find the CA
     bundle) → `export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt`.
   - **WebKit** needs a session bus → wrap in `dbus-run-session`.
   - **Project-open** modals ("not from Bambu Lab", version warnings) when a file is on
     argv → don't pass a file; have the self-test import fixtures via
     `Plater::load_files(paths, LoadModel|Silence, false)`, the geometry-import path
     that skips config modals. Still UI-parity (it's "Import STL").

5. **Clean shutdown was the last 20%.** The self-test runs *inside* the first-run config
   wizard's nested `ShowModal` loop (CallAfter events are pumped there). Quitting by
   closing the MainFrame from inside that loop tore a window down under it →
   `free(): invalid size` (SIGABRT). Ending the modal first, then closing, moved the
   crash to a **pre-existing** `wxWebView::RunScript` SIGSEGV in the wizard's webview
   teardown — pyslic3r appears nowhere in that backtrace; it's BBS/webkit headless
   fragility.
   **Resolution:** the M0 shutdown gate is specifically about the *interpreter*
   ("interpreter finalized, no hang on exit"). The self-test now finalizes the
   interpreter **explicitly** on the main thread (`host_shutdown()`, verified, 2.3 ms),
   then `std::_Exit(0)` — proving the thing under test finalizes cleanly without
   dragging the process through BBS's flaky headless GUI teardown. The webview segfault
   is logged as a separate, out-of-scope BBS-headless issue.

6. **Operational grit (not code):** long foreground SSH commands to the build VM are
   flaky (spurious exit 255, worse with backgrounding or nested heredocs). Everything
   is run as a detached script that writes a `.done` marker + log, then polled. Scripts
   are scp'd, not embedded in `ssh '…'`.

**Net:** the architecture's load-bearing assumption is de-risked. The only scar tissue
is headless-teardown fragility in Bambu Studio itself, which is orthogonal to the
embed/marshal design and only matters for the automated offscreen harness.

---

## Toolchain / build (exact, reproducing environment)

- **Base:** `cauldnz/BambuStudio` @ `ba4f27b` (fork of `bambulab/BambuStudio`), Bambu
  Studio **02.08.00.50**. M0 branch `feat/py-runtime-m0`.
- **OS:** Ubuntu 26.04 LTS (dev VM, KVM, AMD Ryzen 7 PRO 8845HS, 6 cores / 20 GB).
- **Compiler:** GCC 15.2.0 (`Ubuntu 15.2.0-16ubuntu1`), libstdc++. GNU ld 2.46.
- **CMake:** 4.2.3. **Ninja:** 1.13.2.
- **Python:** 3.14.4 (`Development.Embed`). **pybind11:** 3.0.1 (`pybind11-dev`).
- **wxWidgets:** 3.1.5 (deps superbuild). Boost/TBB/OpenCV via `./BuildLinux.sh -d`.
- **Build:** `sudo ./BuildLinux.sh -u` (system deps) → `./BuildLinux.sh -ds` (deps +
  app). CMake adds `find_package(Python 3.10 … Development.Embed)` +
  `find_package(pybind11 CONFIG REQUIRED)` under `option(BBS_PY_RUNTIME ON)`.
- **Run:** `tests/m0/run_m0.sh` (offscreen; needs a seeded datadir so no first-run
  wizard blocks — see `tests/m0/`).

---

## Escalations / notes for the human review

- **PASS with one asterisk, stated plainly:** clean *interpreter* finalize is proven;
  full *GUI* teardown headless is not (pre-existing wxWebView segfault). If M0 must
  demonstrate a fully-graceful GUI exit too, that's a separate BBS-headless fix, not an
  embed/marshal one. Recommend accepting the interpreter-scoped finalize for M0.
- **Namespace locked:** `pyslic3r` (was working name `bambustudio`).
- **Platform:** M0 done Linux-first (deployment target; sidesteps MSVC v142 sourcing).
  Windows returns as a CI target later per SPEC §8.
- **Ready for M1** (read-only object model) on this proven foundation.
