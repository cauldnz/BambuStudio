"""M2 mutation assertions, run in-process by the self-test on the wx main
thread. Each mutation routes through Plater (UI-parity, undo snapshots); every
effect is verified through the M1 read-only getters. Raises on failure.

Starts from the 2-cube fixture (M1 state). Uses PYSLIC3R_M2_ADD_FILE for the
model to add (a third cube).
"""
import os
import pyslic3r

app = pyslic3r.app
doc = app.active_document
model = doc.model

add_file = os.environ["PYSLIC3R_M2_ADD_FILE"]

# --- baseline -------------------------------------------------------------
assert model.object_count == 2, f"expected 2 objects to start, got {model.object_count}"

# --- add ------------------------------------------------------------------
new_obj = model.add(add_file)
assert model.object_count == 3, f"after add, object_count {model.object_count} != 3"
assert new_obj.name, "added object has no name"

# --- translate (verify via instance-aware bounding box) -------------------
obj = model.objects[0]
bb0 = obj.bounding_box()
dx, dy, dz = 12.0, -7.0, 0.0
obj.translate(dx, dy, dz)
bb1 = obj.bounding_box()
for i, d in enumerate((dx, dy, dz)):
    got = bb1["min"][i] - bb0["min"][i]
    assert abs(got - d) < 1e-6, f"axis {i}: bbox min moved {got}, expected {d}"

# --- remove ---------------------------------------------------------------
model.remove(model.objects[2])
assert model.object_count == 2, f"after remove, object_count {model.object_count} != 2"

# --- config.set (process/print preset) ------------------------------------
pc = doc.print_config
if pc.has("layer_height"):
    assert not pc.is_dirty, "print preset dirty before edit"
    pc.set("layer_height", "0.28")
    got = float(pc.get("layer_height"))
    assert abs(got - 0.28) < 1e-9, f"layer_height read back {got} != 0.28"
    assert pc.is_dirty, "print preset not dirty after edit"
    _M2_CONFIG_TESTED = True
else:
    _M2_CONFIG_TESTED = False

# global config is derived/read-only: set must be refused
try:
    doc.config.set("layer_height", "0.3")
    raise AssertionError("global config.set should have raised")
except RuntimeError:
    pass

# --- apply_preset (machine) ----------------------------------------------
printers = app.printers()
cur = app.selected_printer
alt = next((p for p in printers if p != cur), None)
if alt is not None:
    doc.printer_config.apply_preset(alt)
    assert app.selected_printer == alt, \
        f"selected_printer {app.selected_printer!r} != applied {alt!r}"
    _M2_PRESET_TESTED = True
else:
    _M2_PRESET_TESTED = False

# --- arrange (async: just confirm it starts cleanly and keeps objects) ----
doc.plates.arrange()
assert model.object_count == 2, "arrange changed object count unexpectedly"

print(f"M2 verify OK: add/translate/remove/config.set(dirty={_M2_CONFIG_TESTED})/"
      f"apply_preset(tested={_M2_PRESET_TESTED})/arrange all via Plater")
