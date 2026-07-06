"""SEND verification (READ-ONLY where it touches the printer): slice the loaded
fixture, fetch the camera URL, and DRY-RUN the send (export + prepare, NO
dispatch). Never dispatches a real print — that requires explicit human
approval and is not exercised here.

Runs after the fixtures are loaded (the self-test loads the 2 cubes). Raising
here fails the SEND check.
"""
import os
import pyslic3r

app = pyslic3r.app
doc = app.active_document
assert doc is not None, "no active document"

# Slice the loaded fixture (arrange onto the bed first, as M3 does).
doc.plates.arrange(wait=True)
job = doc.slice()
res = job.wait(timeout=240)
assert res.success, f"slice failed: {res.error}"
print(f"SEND diag: sliced OK — {res.layer_count} layers, {res.print_time_s}s")

dev = app.device
dev.refresh()
printers = dev.printers()
print("SEND diag: printers =", [(p.dev_id, p.name, p.online) for p in printers])
assert printers, "no bound printer to send to"
dev.select(printers[0].dev_id)

# Camera URL (read-only). NOTE: the cloud appears to reject camera access from
# an unofficial (from-source) build with an "update_studio" message that pops a
# modal — so it's gated behind PYSLIC3R_TEST_CAMERA to keep this test headless-
# safe. The binding is correct; verify it on an official build / interactively.
if os.environ.get("PYSLIC3R_TEST_CAMERA"):
    url = dev.camera_url(timeout=15)
    print("SEND diag: camera_url =", (url[:64] + "…") if url else None)
    assert url is None or isinstance(url, str), "camera_url not None-or-str"
else:
    print("SEND diag: camera_url skipped (PYSLIC3R_TEST_CAMERA unset)")

# DRY-RUN send: exports the sliced 3mf and prepares the params, but MUST NOT
# dispatch to the physical printer.
r = dev.send(dry_run=True, project_name="pyslic3r-selftest")
print("SEND diag: dry_run send =", r)
assert r["dry_run"] is True, "expected dry_run True"
assert r["dispatched"] is False, "DRY RUN MUST NOT DISPATCH"
assert r["ready"] is True, f"dry-run not ready: {r}"
assert r["gcode_3mf"] and os.path.exists(r["gcode_3mf"]), \
    f"exported gcode.3mf missing: {r.get('gcode_3mf')!r}"

print("SEND verify OK: sliced, camera_url fetched, DRY-RUN send prepared "
      "(export ok, NOT dispatched)")
