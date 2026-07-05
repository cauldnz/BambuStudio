# M3-RESULT — Slicing

**RESULT: PASS** — 10/10 checks, harness exit 0, clean interpreter finalize. The agent
slices the fixture offscreen and reads back time / layers / filament / gcode path.

Milestone M3 from `slic3r-automation/M3-PLAN.md`. This was the first milestone that
actually runs the slicer headless; it took real integration work (see "What fought
back"), unlike M1/M2 which passed first build.

---

## Checks (latest run)

- PASS — setup / path (a) / path (b) (M0 marshalling, 1000/1000 stable)
- PASS — M1 read-only object model · PASS — M2 mutation
- PASS — **M3: slicing asserts** (slice → wait → read-back)
- PASS — interpreter finalized cleanly

**Slice result (two 10 mm cubes, 0.28 mm layers, X1C / PLA):**
643 s · 36 layers · **1.71 g / 564 mm** filament · gcode written. All internally
consistent (36 × 0.28 mm ≈ 10 mm cube height; the 0.28 mm came from M2's
`config.set("layer_height","0.28")` earlier in the same run).

## Surface delivered

```
doc.slice(plate=None) -> SliceJob      # reslice current/selected plate
job.wait(timeout)     -> SliceResult   # blocks caller, pumps the event loop
job.done / job.progress / job.cancel()
result.success / print_time_s / layer_count / filament_g / filament_mm /
       gcode_3mf_path / error
plates.arrange(wait=True)              # M2's arrange, now optionally synchronous
```

## The async design (the load-bearing part)

`job.wait()` runs on the wx main thread (where Python runs in this model), **releases the
GIL**, and pumps the event loop (`wxTheApp->Yield` + poll
`PartPlate::is_slice_result_valid()`) until the background slicer's completion event
lands — a *controlled event pump*, not a nested modal loop (the M0 crash class). It
classifies "never started" / "started then errored" / "timeout" into `result.error`.
`plates.arrange(wait=True)` reuses the same pump, polling `Plater::is_any_job_running()`.
Verified: the slice worker runs, its completion is delivered, and the main loop is never
blocked.

## What fought back (the whole story — this milestone was the hard one)

1. **Nothing was sliceable because no printer was installed.** The seed datadir only had
   the placeholder "Default Printer" (no build volume / extruders). Diagnostics made this
   legible (`printers = ['Default Printer']`, `is_sliceable = False`).
2. **The UI-parity path to fix it crashes headless.** `apply_preset(force=True)` →
   `Tab::select_preset` SIGSEGVs offscreen — it drives ObjectList/ObjectSettings widgets
   that aren't populated headless (`… → TabPrintModel::update_model_config → variant_keys
   → SIGSEGV`). **`Tab`-driven preset selection is not headless-safe** — a finding that
   matters for M5 and that also means M2's `apply_preset` (skipped in its run) is
   unverified/unsafe via the Tab.
3. **Naming a preset in the config doesn't install it.** Setting `presets.machine` to the
   X1C name fell back to "Default Printer": at load the app drops a selected preset that
   isn't *installed/visible*.
4. **Fixed properly by replicating what the wizard persists** (`tests/m3/install_printer.py`,
   committed and reproducible). A printer preset is visible iff
   `AppConfig::get_variant(vendor_id, model, variant)` is true
   (`Preset::set_visible_from_appconfig`); the JSON app config encodes that as a
   `"models"` array (`{"vendor":"BBL","model":"Bambu Lab X1 Carbon","nozzle_diameter":"0.4"}`)
   and installed filaments as a `"filaments"` array. `vendor_id` is the vendor profile's
   filename stem ("BBL"); model/variant come from the machine preset's
   `printer_model`/`printer_variant`. With the X1C installed + a compatible process
   (`0.20mm Standard @BBL X1C`) and filament (`Bambu PLA Basic @BBL X1C`) selected, the
   config is valid.
5. **`is_sliceable` before slicing is a red herring.** `PartPlate::can_slice()` is
   `m_ready_for_slice && !m_apply_invalid`, flags only computed once the background
   process is applied — which `reslice()` itself does. So it reads False *before* the
   first slice; don't gate on it.
6. **Objects load off the printable area.** They come in at raw STL coordinates
   (e.g. min (7,-12,0)); the plate wasn't ready until they were placed. `arrange(wait=True)`
   onto the bed made the plate genuinely sliceable → `is_sliceable = True` → slice ran.
7. **Filament units bug, caught by a sanity bound.** `PrintStatistics::filament_stats` is
   actually **volume (mm³)**, not grams (`= model_volumes_per_extruder`). The first green
   run reported "1357 g". Now computed correctly: grams = volume(cm³) × density(g/cm³)
   (per-extruder `GCodeProcessorResult::filament_densities`), mm = volume / Ø1.75 mm
   cross-section → **1.71 g / 564 mm**. `verify_m3.py` now bounds grams `< 100` so a
   volume-vs-grams regression can't pass again.

Also fixed a **latent harness bug** (valuable regardless of M3): every pass/fail path now
routes through `finalize_and_exit()`. Previously a failed milestone wrote its result but
never `_Exit`'d (that lived only in the path-(b) finale), hanging to the timeout.

## Deferred to later milestones (documented)

- **Push progress/complete events** to Python callbacks / MCP notifications — M5. M3
  progress is pollable (`job.progress`, `job.done`); the slice itself is fully synchronous
  via `wait()`.
- **Multi-plate "slice all"** — M3 slices the current/selected plate (the fixture is
  single-plate). The plate-select plumbing is in `doc.slice(plate=idx)`.

## Follow-ups worth surfacing

- **`Tab`-driven preset selection is headless-unsafe.** `apply_preset` should be
  re-pointed at a non-Tab path (low-level `PresetCollection::select_preset_by_name` +
  `Plater::on_config_change`) or gated, before M5 exercises it. Tracked here and in
  M2-RESULT.
- The seed datadir is provisioned by `tests/m3/install_printer.py` against a base datadir
  produced by a first app run; documented in that script.

## Environment

BambuStudio 02.08.00.50 · Python 3.14.4 · pybind11 3.0.1 · wxWidgets 3.1.5 · GCC 15.2.0 ·
Ubuntu 26.04 (KVM). Branch `feat/py-runtime-m3` off `feat/py-runtime-m2`.
