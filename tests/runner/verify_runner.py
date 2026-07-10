"""Automated test for the pyslic3r script runner (PYSLIC3R_SCRIPT).

Runs as a standalone user script (NOT via the self-test harness) — so it must
set up its own state (the runner does not preload fixtures). Adds a model,
reads it back, and asserts. Raising here makes the runner print
'PYSLIC3R_SCRIPT: ERROR' and exit non-zero.
"""
import os
import pyslic3r

app = pyslic3r.app
assert app.version, "app.version empty"

doc = app.active_document
assert doc is not None, "no active document"

before = doc.model.object_count
stl = os.environ["PYSLIC3R_RUNNER_STL"]
obj = doc.model.add(stl)
assert doc.model.object_count == before + 1, \
    f"add did not increase object_count ({before} -> {doc.model.object_count})"

size = obj.bounding_box()["size"]
assert all(v > 0 for v in size), f"degenerate bounding box {size}"

# Config read-back works from a user script too.
assert isinstance(doc.print_config.keys(), list), "print_config.keys() not a list"

print(f"RUNNER OK: version={app.version}, added {obj.name!r}, "
      f"size={tuple(round(v, 1) for v in size)}, "
      f"object_count={doc.model.object_count}")
