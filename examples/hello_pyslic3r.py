"""hello_pyslic3r.py — a tiny script that drives BambuStudio through the
embedded pyslic3r runtime.

Run it against a running BambuStudio built with the pyslic3r runtime:

    # batch mode: do a thing, then exit (headless-friendly)
    PYSLIC3R_SCRIPT=examples/hello_pyslic3r.py PYSLIC3R_SCRIPT_EXIT=1 \
        bambu-studio --datadir <your-datadir>

    # against a live interactive session (leave the app running):
    PYSLIC3R_SCRIPT=examples/hello_pyslic3r.py bambu-studio --datadir <dir>

The script runs once on the app's main thread, so it can touch the live
document directly. Point HELLO_STL at an STL/3MF to add + measure it.
"""
import os
import pyslic3r

app = pyslic3r.app
print(f"BambuStudio version: {app.version}")

doc = app.active_document
if doc is None:
    print("no active document")
else:
    print(f"objects in document: {doc.model.object_count}")
    print(f"plates: {doc.plates.count}")
    lh = doc.print_config.get("layer_height")
    print(f"process layer_height: {lh}")

    stl = os.environ.get("HELLO_STL")
    if stl:
        obj = doc.model.add(stl)                     # import like GUI "Add"
        bb = obj.bounding_box()
        print(f"added {obj.name!r}: size {tuple(round(v, 1) for v in bb['size'])} mm")
        print(f"objects now: {doc.model.object_count}")

# Cloud device plane (read-only) — degrades gracefully if not logged in.
dev = app.device
print(f"device: available={dev.available} logged_in={dev.is_logged_in} "
      f"printers={len(dev.printers())}")

print("hello_pyslic3r done")
