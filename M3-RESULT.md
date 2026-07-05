# M3-RESULT — Slicing

**RESULT: WIP / BLOCKED** — the slicing code is complete, builds clean, and the async
wait design works; it is **blocked on provisioning a sliceable printer in the headless
test environment**. Not yet a PASS. Documented here for review and a decision on the
provisioning approach.

Milestone M3 from `slic3r-automation/M3-PLAN.md`. Unlike M0–M2 (all green), M3 is the
first milestone that actually runs the slicer offscreen, and it surfaced a real
environment problem, not a code defect.

---

## What is DONE and working

- **Full slicing surface** (`PyObjectModel.cpp`), compiles and links clean:
  ```
  doc.slice(plate=None) -> SliceJob      # reslice current/selected plate
  job.wait(timeout)     -> SliceResult   # blocks caller, pumps the event loop
  job.done / job.progress / job.cancel()
  result.success / print_time_s / layer_count / filament_g / filament_mm /
         gcode_3mf_path / error
  ```
- **The async design is implemented and sound.** `job.wait()` runs on the wx main
  thread (where Python runs in this model), releases the GIL, and pumps the event loop
  (`wxTheApp->Yield` + poll `PartPlate::is_slice_result_valid()`) so the background
  slicer's completion event is delivered — a *controlled event pump*, not a nested modal
  loop (the M0 crash class). It distinguishes "never started", "started then errored",
  and "timeout" and reports the reason in `result.error`.
- **Result read-back is wired** to `GCodeProcessorResult::print_statistics` (time,
  layer count, per-extruder volume→mm) and `Print::print_statistics().filament_stats`
  (grams), plus `PartPlate::get_tmp_gcode_path()`.
- **A latent harness bug was fixed** (valuable regardless of M3): on *any* failure the
  self-test wrote the result but never reached `_Exit` (that lived only in the path-(b)
  worker finale), so a failed milestone hung to the timeout. Terminal logic is now a
  single `finalize_and_exit()` used by every pass/fail path. Confirmed: M3 now fails
  cleanly (rc=1), no hang.

## The blocker (well-characterized)

To slice, a plate needs a real printer + compatible process + filament (build volume,
extruders, etc.). The **seed datadir has only the placeholder "Default Printer"** — it
never went through the first-run wizard, which is what *installs* (makes visible) a
vendor's machine presets. Diagnostics from the run:

```
selected_printer = 'Default Printer'
printers         = ['Default Printer']
plate0 is_sliceable = False
```

Two fixes were tried and ruled out:

1. **Runtime UI-parity path — `apply_preset(force=True)` → `Tab::select_preset`:**
   **segfaults headless.** Backtrace: `Tab::select_preset → load_current_preset →
   TabPrinter::on_preset_loaded → … → TabPrint::update →
   ObjectList::part_selection_changed → ObjectSettings::update_settings_list →
   TabPrintModel::update_model_config → variant_keys → SIGSEGV`. The Tab preset cascade
   drives ObjectList/ObjectSettings widgets that aren't populated in an offscreen app.
   So the GUI's own preset-selection path is **not headless-safe**. (This also means
   M2's `apply_preset` — implemented but skipped in that run — is currently unverified;
   corrected in M2-RESULT.)

2. **Name the presets in the datadir config** (`presets.machine =
   "Bambu Lab X1 Carbon 0.4 nozzle"`, etc.): **doesn't stick.** At load the app drops a
   selected preset that isn't *installed/visible* back to "Default Printer". Selection by
   name requires the preset to be installed, not just present in resources.

## Recommended next steps (a decision for review)

In rough order of preference:

1. **Provision the seed datadir with an installed printer, properly.** Replicate what the
   wizard persists: the enabled vendor/model/variant (`AppConfig::set_variant` →
   `PresetBundle::load_installed_printers`) so "Bambu Lab X1 Carbon 0.4 nozzle" is
   *visible*, then select it + a compatible process/filament. Need to pin how BBS stores
   installed vendors in the **JSON** app config (the `[vendor:…]` INI path in
   `AppConfig.cpp` appears to be a separate serialization; the JSON seed has no
   models/vendor section). Cleanest and most UI-faithful.
2. **One-time real datadir capture:** run the fork's GUI once on a desktop, complete the
   wizard picking an X1C, and check the resulting datadir in as the test seed. Pragmatic,
   unblocks immediately, but couples the test to a captured profile.
3. **Low-level `PresetBundle::…select_preset_by_name(name, force, select_invisible=true)`
   for all three collections**, bypassing the crashing Tab, then push to Plater via
   `on_config_change`. Avoids the wizard but skips the Tab's compatibility cascade — must
   select a mutually-compatible trio by hand and verify the plate turns sliceable.

Once a printer is installed/selected, `verify_m3.py` (already written) should slice the
two-cube fixture and read back time/layers/filament unchanged.

## Also flagged for the design

`Tab::select_preset` being headless-unsafe is a broader signal: **preset selection and
anything that refreshes the object-settings UI can't be driven offscreen through the Tab
layer.** M2's `apply_preset` should be re-pointed at a headless-safe path (option 3
above) or gated. Worth resolving before M5 (the bridge will exercise these).

## Environment

BambuStudio 02.08.00.50 · Python 3.14.4 · pybind11 3.0.1 · wxWidgets 3.1.5 · GCC 15.2.0 ·
Ubuntu 26.04 (KVM). Branch `feat/py-runtime-m3` off `feat/py-runtime-m2`.
