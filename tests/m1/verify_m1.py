"""M1 read-only object-model assertions, run in-process by the self-test
(py::eval_file) on the wx main thread. Raises AssertionError on any failure;
returning normally means PASS. Exercises the whole read surface against the
two-cube fixture (expected 2 objects).
"""
import pyslic3r

app = pyslic3r.app

# --- Application ----------------------------------------------------------
assert isinstance(app.version, str) and app.version, "app.version empty"
printers = app.printers()
assert isinstance(printers, list), "app.printers() not a list"
# selected_printer is a string (may be empty on a bare profile); just type-check.
assert isinstance(app.selected_printer, str), "selected_printer not str"

# --- Document -------------------------------------------------------------
doc = app.active_document
assert doc is not None, "no active document"
assert doc.object_count == 2, f"object_count {doc.object_count} != 2"

# --- Model / Objects / Volumes -------------------------------------------
model = doc.model
assert model.object_count == 2, f"model.object_count {model.object_count} != 2"
objs = model.objects
assert len(objs) == 2, f"len(objects) {len(objs)} != 2"

for o in objs:
    assert isinstance(o.name, str), "object.name not str"
    assert o.instance_count >= 1, f"object {o.name} has no instances"
    vols = o.volumes
    assert len(vols) >= 1, f"object {o.name} has no volumes"
    for v in vols:
        assert isinstance(v.name, str), "volume.name not str"
        assert isinstance(v.type, str) and v.type, "volume.type empty"
    bb = o.bounding_box()
    for key in ("min", "max", "size", "center"):
        assert key in bb and len(bb[key]) == 3, f"bbox missing {key}"
    sx, sy, sz = bb["size"]
    assert sx > 0 and sy > 0 and sz > 0, f"degenerate bbox size {bb['size']}"

# --- Plates ---------------------------------------------------------------
plates = doc.plates
assert plates.count >= 1, f"plates.count {plates.count} < 1"
assert len(plates) == plates.count, "plates len mismatch"
p0 = plates[0]
assert p0.index == 0, "plate[0].index != 0"
assert p0.object_count >= 0, "plate object_count negative"
assert isinstance(p0.is_sliceable, bool), "is_sliceable not bool"

# --- Config ---------------------------------------------------------------
cfg = doc.config
keys = cfg.keys()
assert isinstance(keys, list) and len(keys) > 0, "config has no keys"
# has()/keys()/get() must agree.
sample = keys[0]
assert cfg.has(sample), f"has({sample}) false but in keys()"
assert cfg.get(sample) is not None, f"get({sample}) None but has() true"
assert not cfg.has("definitely_not_a_real_key_xyz"), "has() true for bogus key"
assert cfg.get("definitely_not_a_real_key_xyz") is None, "get() non-None for bogus key"

# A known process key should be present and read back non-empty.
if cfg.has("layer_height"):
    assert cfg.get("layer_height"), "layer_height empty"

# The three preset-config views resolve and expose keys.
for name in ("print_config", "filament_config", "printer_config"):
    c = getattr(doc, name)
    assert isinstance(c.keys(), list), f"{name}.keys() not a list"

print(f"M1 verify OK: 2 objects, {plates.count} plate(s), "
      f"{len(keys)} global config keys, {len(printers)} visible printer(s)")
