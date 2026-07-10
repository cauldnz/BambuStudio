"""P2S gate-test PREP (dry-run only — NO dispatch). Slice the 20 mm cube with
the P2S presets, select the P2S, and dry-run the send (AMS slot 1). Reports the
print estimate so the human can approve the real dispatch separately.
"""
import pyslic3r

app = pyslic3r.app
doc = app.active_document
assert doc is not None, "no active document"

print("P2S diag: printer preset =", repr(app.selected_printer))

doc.plates.arrange(wait=True)
job = doc.slice()
res = job.wait(timeout=300)
assert res.success, f"slice failed: {res.error}"
grams = round(sum(res.filament_g.values()), 2)
print(f"P2S diag: sliced OK — {res.layer_count} layers, {res.print_time_s}s "
      f"(~{res.print_time_s // 60} min), ~{grams} g filament")

dev = app.device
dev.refresh()
printers = dev.printers()
print("P2S diag: printers =", [(p.dev_id, p.name, p.online) for p in printers])
assert printers, "no bound printer"
p = printers[0]
dev.select(p.dev_id)

# DRY-RUN: prepare the send for AMS slot 1 (tray index 0), single filament.
r = dev.send(dry_run=True, project_name="pyslic3r-p2s-cube",
             use_ams=True, ams_mapping="[0]")
print("P2S diag: DRY-RUN send =", r)
assert r["dry_run"] is True and r["dispatched"] is False, "dry-run must not dispatch"
assert r["ready"] is True, f"not ready: {r}"

print(f"P2S DRYRUN OK: sliced + prepared for dispatch "
      f"({res.print_time_s // 60} min, ~{grams} g) — NOT dispatched")
