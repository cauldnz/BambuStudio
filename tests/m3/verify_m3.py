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
# filament installed & selected (see tests/m3/install_printer.py), so slicing
# has a valid config without any runtime preset switching (Tab::select_preset
# is not headless-safe — see M3-RESULT).
#
# NOTE: plate.is_sliceable (PartPlate::can_slice -> m_ready_for_slice) only
# becomes true AFTER the background process is applied/validated, which
# reslice() itself does — so it reads False here, before the first slice.
# Don't gate on it; call slice() and judge by the result.

# Objects load at their raw STL coordinates, which may sit off the printable
# area — arrange them onto the bed first (synchronously) so the plate is
# actually sliceable, then slice.
for o in doc.model.objects:
    bb = o.bounding_box()
    print("M3 diag: object", repr(o.name), "min", bb["min"], "max", bb["max"])
print("M3 diag: arranging...")
doc.plates.arrange(wait=True)
print("M3 diag: after arrange, plate0 is_sliceable =", doc.plates[0].is_sliceable)

job = doc.slice()                     # slice the current plate
result = job.wait(timeout=240)        # blocks here, pumping events, until done
print("M3 diag: slice success =", result.success, "error =", repr(result.error))

assert result.success, f"slice did not complete: {result.error}"
assert result.print_time_s > 0, f"print_time_s = {result.print_time_s}"
assert result.layer_count > 0, f"layer_count = {result.layer_count}"
assert result.gcode_3mf_path, "no gcode path reported"

total_g = sum(result.filament_g.values())
total_mm = sum(result.filament_mm.values())
# Two 10 mm cubes: a couple of grams / a few metres. Sanity-bound the units so a
# volume-vs-grams regression can't pass (a 1 kg spool is 1000 g).
assert 0 < total_g < 100, f"filament grams out of range: {result.filament_g}"
assert total_mm > 0, f"filament mm not positive: {result.filament_mm}"

print(f"M3 verify OK: {result.print_time_s}s, {result.layer_count} layers, "
      f"filament {total_g:.2f} g / {total_mm:.0f} mm (per-slot g={result.filament_g}), "
      f"gcode={result.gcode_3mf_path!r}")
