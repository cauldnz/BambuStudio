"""M3 slicing assertions, run in-process by the self-test on the wx main
thread. Slices the loaded fixture and reads back the result. job.wait() pumps
the wx event loop (GIL released) so the background slicer's completion is
delivered — it does not block the loop it depends on. Raises on failure.

Prints diagnostics to stdout (captured in m3-run.log) to make a slice failure
legible.
"""
import pyslic3r

app = pyslic3r.app
doc = app.active_document
assert doc is not None, "no active document"
assert doc.model.object_count == 2, f"expected 2 objects, got {doc.model.object_count}"

# Diagnostics: what's the slicing config + plate state before we slice?
print("M3 diag: selected_printer =", repr(app.selected_printer))
print("M3 diag: printers =", app.printers())
p0 = doc.plates[0]
print("M3 diag: plate0 object_count =", p0.object_count,
      "is_sliceable =", p0.is_sliceable)

# The seed datadir boots with a concrete X1C machine + compatible process +
# filament selected (see tests/m3 seed notes), so the plate is sliceable
# without any runtime preset switching. (Runtime Tab::select_preset is not
# headless-safe — it drives ObjectList/ObjectSettings widgets that aren't
# populated offscreen; see M3-RESULT.)
assert p0.is_sliceable, (
    "plate not sliceable — seed datadir needs a real printer/process/filament "
    "selected (selected_printer=%r)" % app.selected_printer)

job = doc.slice()                     # slice the current plate
result = job.wait(timeout=240)        # blocks here, pumping events, until done
print("M3 diag: slice success =", result.success, "error =", repr(result.error))

assert result.success, f"slice did not complete: {result.error}"
assert result.print_time_s > 0, f"print_time_s = {result.print_time_s}"
assert result.layer_count > 0, f"layer_count = {result.layer_count}"
assert any(v > 0 for v in result.filament_g.values()), \
    f"no filament used: {result.filament_g}"
assert result.gcode_3mf_path, "no gcode path reported"

print(f"M3 verify OK: {result.print_time_s}s, {result.layer_count} layers, "
      f"filament_g={result.filament_g}, gcode={result.gcode_3mf_path!r}")
