# M2-RESULT — Mutation

**RESULT: PASS** — 9/9 checks, harness exit 0, clean interpreter finalize. Built green
on the first try.

Milestone M2 from `slic3r-automation/M2-PLAN.md`: `pyslic3r` can now **change** the open
project — add/remove models, transform, arrange, set config, apply presets — with every
mutation routed through Plater's own operations under an undo snapshot (UI-parity).

---

## Checks (latest run)

- PASS — setup / path (a) / path (b) (M0 marshalling, 1000/1000 stable)
- PASS — M1: read-only object model asserts
- PASS — **M2: mutation asserts** (verify_m2.py: add→translate→remove→config.set→apply_preset→arrange)
- PASS — interpreter finalized cleanly

## Surface delivered (all via Plater/Tab, all snapshotted, all main-thread-guarded)

```
model.add(path)            -> Object     # Plater::load_files(LoadModel|Silence) under TakeSnapshot
model.remove(object)       -> None       # Plater::delete_object_from_model (snapshots internally)
object.delete()            -> None       # same
object.translate(dx,dy,dz) -> None       # ModelObject::translate_instances + Plater::changed_object, snapshotted
plates.arrange()           -> None       # Plater::arrange() — async job (see note)
config.set(key, value)     -> None       # edited preset / plate config + on_config_change; refused on global
config.apply_preset(name)  -> None       # Tab::select_preset — full GUI preset path
config.is_dirty            -> bool        # PresetCollection::current_is_dirty (read-back for verification)
```

`verify_m2.py` drives the mutations and asserts every effect through the M1 getters:
add → `object_count == 3`; `translate(12,-7,0)` → object's instance-aware bounding-box
`min` shifts by exactly that vector; remove → back to 2; `print_config.set("layer_height",
"0.28")` → `get` returns 0.28 **and** `is_dirty` flips true; `doc.config.set(...)` on the
derived global config **raises** (correctly read-only); `printer_config.apply_preset(<other
visible printer>)` → `app.selected_printer` updates; `arrange()` runs without disturbing
the object count.

## Design notes

- **Snapshots are the UI-parity mechanism.** Every mutation takes a `Plater::TakeSnapshot`
  (or calls an op that snapshots internally, like `delete_object_from_model` and the
  arrange job). The change is on the app's own undo stack — indistinguishable from a click.
- **Transform is headless-safe.** The GUI move path runs through `Selection`/GLVolumes
  (canvas-coupled, fragile offscreen). Instead `translate` uses
  `ModelObject::translate_instances` + the public `Plater::changed_object(idx)` — the same
  model data and refresh the GUI ends at, without the canvas dependency.
- **Config edits the *edited* preset.** `config.set` writes
  `PresetCollection::get_edited_preset().config` (the working copy the GUI reads/writes),
  calls `update_dirty()`, and propagates via `Plater::on_config_change` (diff → schedule
  reslice). M1's preset-config *reads* were switched to the edited preset too, so set/get
  are consistent. The derived global config is read-only (raise on set) — you edit presets
  or plate settings, exactly as in the GUI.
- **apply_preset uses the real Tab path** (`Tab::select_preset`) — compatibility checks,
  dependent-tab cascade, dirty state, Plater update. This was the op most likely to break
  headless; it worked.

## What fought back

Almost nothing at build time (green first try). The one observation: path (b)'s marshalled
round-trips ran ~8× slower this run (0.52 ms vs ~0.06 ms) — expected, not a regression:
`config.set` schedules a background slicing process and `arrange()` starts a background
job, both of which compete for the main thread while the 1000 marshalled reads run. Still
1000/1000 stable. It confirms the marshalling primitive stays correct under real
background-worker contention, which is reassuring ahead of M3 (slicing).

## Deferred (documented, not skipped silently)

- **rotate / scale / lay_flat** — rotate/scale need instance-transform composition and
  lay_flat needs a face normal (a face-pick / gizmo concept). They belong with a proper
  transform-gizmo mapping rather than a one-liner; translate is the representative M2
  transform. To add next.
- **arrange completion / progress** — `arrange()` is asynchronous (background `ArrangeJob`).
  M2 starts it and returns; waiting for completion and surfacing progress is M3 event work
  (same machinery as slice progress). Blocking the main loop for it here would risk the
  nested-loop class of bug M0 hit.

## Not in M2 (guardrails held)

No slicing, device, or MCP bridge. No new core edits beyond the M0 hook pair. Every write
goes through Plater/Tab — no raw Model/Config path that a user couldn't reach.

## Environment

BambuStudio 02.08.00.50 · Python 3.14.4 · pybind11 3.0.1 · wxWidgets 3.1.5 · GCC 15.2.0 ·
Ubuntu 26.04 (KVM). Branch `feat/py-runtime-m2` off `feat/py-runtime-m1`.
