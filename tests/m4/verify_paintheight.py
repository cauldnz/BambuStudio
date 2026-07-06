"""Paint-by-height bench test (slicing only, no printer)."""
import pyslic3r
app = pyslic3r.app
doc = app.active_document

doc.plates.arrange(wait=True)
base = doc.slice().wait(timeout=300)
assert base.success, base.error
print(f"PAINT: baseline {base.layer_count} layers")

# --- height-range modifier: finer layers in the 4-8mm band ---
obj = doc.model.objects[0]
r = obj.add_height_range(4.0, 8.0, {"layer_height": "0.10"})
print("PAINT: added height range", r, "->", obj.height_ranges())
hr = doc.slice().wait(timeout=300)
assert hr.success, hr.error
print(f"PAINT: with height range = {hr.layer_count} layers (baseline {base.layer_count})")
assert hr.layer_count > base.layer_count, "finer middle band should add layers"
obj.clear_height_ranges()
print("PAINT: cleared ranges ->", obj.height_ranges())

# --- colour-change-by-height ---
plate = doc.plates[0]
plate.set_color_changes([
    {"z": 4.0, "extruder": 1, "color": "#E01B24"},
    {"z": 8.0, "extruder": 1, "color": "#1A5FB4"},
])
cc = plate.color_changes()
print("PAINT: color_changes read-back =", cc)
assert len(cc) == 2 and abs(cc[0]["z"]-4.0) < 1e-6 and abs(cc[1]["z"]-8.0) < 1e-6, cc
cs = doc.slice().wait(timeout=300)
assert cs.success, cs.error
print(f"PAINT: sliced with {len(cc)} colour changes -> {cs.layer_count} layers OK")
plate.clear_color_changes()
assert plate.color_changes() == [], "clear failed"
print("PAINT PASS")
