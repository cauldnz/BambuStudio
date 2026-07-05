# M1-RESULT — Read-only object model

**RESULT: PASS** — 8/8 checks, harness exit 0, clean interpreter finalize. Built green
on the first try on the M0 foundation.

Milestone M1 from `slic3r-automation/M1-PLAN.md`: expand `pyslic3r` from the two M0 stub
members to a full **read-only** object model — the agent can now inspect an open
project (application, document, model tree, config, plates) but cannot mutate anything.

---

## Checks (latest run)

- PASS — setup: imported 2 fixture(s)
- PASS — path (a): import pyslic3r
- PASS — path (a): app.version non-empty ("02.08.00.50")
- PASS — path (a): active_document present
- PASS — path (a): object_count == 2
- PASS — **M1: read-only object model asserts passed** (verify_m1.py walked the tree)
- PASS — path (b): background thread, 1000/1000 marshalled round-trips, values stable
- PASS — interpreter finalized cleanly (explicit host_shutdown)

## Timings

| what | value |
|---|---|
| interpreter init | 9.90 ms |
| path (a): main-thread import + reads | 0.17 ms |
| path (b): 1000/1000 × 2 marshalled reads | 135.30 ms (0.068 ms/round-trip) |
| interpreter finalize | 2.67 ms |

---

## Surface delivered (all read-only, all via Plater/PresetBundle)

```
app.version · app.printers() · app.selected_printer · app.active_document
doc.object_count · doc.model · doc.plates
doc.config · doc.print_config · doc.filament_config · doc.printer_config
model.object_count · model.objects
object.name · object.instance_count · object.volumes · object.bounding_box()  # {min,max,size,center}
volume.name · volume.type · volume.is_model_part
plates.count · plate.index · plate.object_count · plate.is_sliceable · plate.config
config.get(key) · config.has(key) · config.keys()
```

`verify_m1.py` (run in-process on the main thread) asserts the whole tree against the
two-cube fixture: 2 objects each with ≥1 volume and a non-degenerate bounding box,
≥1 plate, and `has()`/`keys()`/`get()` mutual consistency (incl. a bogus key returning
`False`/`None`). Path (b) additionally proves the reads round-trip through the M0
marshalling primitive from a background thread.

## Design notes

- **Index handles, not raw pointers.** Every wrapper (`PyObject`, `PyVolume`, `PyPlate`,
  …) stores indices and re-resolves the live C++ object per call, bounds-checked. A
  stale Python handle raises cleanly instead of dereferencing freed memory if the model
  changes — important once M2 introduces mutation.
- **One guard everywhere.** Each accessor asserts the wx main thread (`main_thread()`),
  so off-thread/bridge callers must come through `run_on_main_blocking()`. Verified by
  path (b).
- **Config plumbing.** `doc.config` is Plater's effective global config;
  print/filament/printer views are the selected presets' `DynamicPrintConfig`
  (`PresetBundle`). Values are read via `opt_serialize(key)` (string form) — uniform and
  read-only.
- **Isolation held.** All new code is in `src/slic3r/Scripting/` (`PyObjectModel.cpp` +
  `PyBindings.hpp`); `PyHost.cpp`'s module macro is now a thin composition point. Zero
  new core edits beyond the M0 hook pair.

## What fought back

Very little — the M0 work (headless run, GIL/wx marshalling, clean exit) had already
cleared the hard ground, so M1 was additive bindings on a proven harness and passed on
the first build. The only real effort was mapping exact current BambuStudio signatures
(Plater config/plate accessors, Model tree fields, `PresetBundle` preset enumeration,
`BoundingBoxf3`) before writing bindings, which avoided compile churn.

## Not in M1 (guardrails held)

No mutation, no `add_model`/`transform`/`arrange`, no `Config.set`, no slicing/device/MCP.
Those are M2+.

## Environment

BambuStudio 02.08.00.50 · Python 3.14.4 · pybind11 3.0.1 · wxWidgets 3.1.5 · GCC 15.2.0 ·
Ubuntu 26.04 (KVM). Branch `feat/py-runtime-m1` off `feat/py-runtime-m0`.
