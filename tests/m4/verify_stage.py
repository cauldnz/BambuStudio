"""STAGE test — upload the sliced 20 mm cube to the P2S WITHOUT starting a print.

This exercises device.stage() (the app's "Send to Printer" primitive,
start_send_gcode_to_sdcard): it places the sliced 3mf on the printer's storage
so the human starts it themselves from the printer screen or Bambu Handy. It
NEVER issues a start-print command.

Dry-run always runs (fully local, no device write). The real upload only runs
when PYSLIC3R_DO_STAGE=1 — and even then, no print starts.
"""
import os
import pyslic3r

app = pyslic3r.app
doc = app.active_document
assert doc is not None, "no active document"

doc.plates.arrange(wait=True)
res = doc.slice().wait(timeout=300)
assert res.success, f"slice failed: {res.error}"
print(f"STAGE: sliced {res.layer_count} layers, ~{res.print_time_s // 60} min")

dev = app.device
dev.refresh()
printers = dev.printers()
assert printers, "no bound printer"
dev.select(printers[0].dev_id)

st = dev.status(wait=20)
print("STAGE: pre-stage connected =", st.get("connected"))

# DRY-RUN: export + prepare, no upload.
r = dev.stage(dry_run=True, project_name="pyslic3r-p2s-cube",
              use_ams=True, ams_mapping="[0]")
print("STAGE dry-run =", r)
assert r["dry_run"] is True and r["staged"] is False, "dry-run must not stage"
assert r["ready"] is True, f"not ready: {r}"
print("STAGE: connection =", r.get("connection"),
      "| printer supports send-to-sdcard =", r.get("supports_sdcard"))

if os.environ.get("PYSLIC3R_DO_STAGE") == "1":
    print("STAGE: uploading to the printer's storage (NO print start) ...")
    r2 = dev.stage(dry_run=False, project_name="pyslic3r-p2s-cube",
                   use_ams=True, ams_mapping="[0]")
    print("STAGE real =", r2)
    if r2.get("staged"):
        print("STAGE OK: file is on the printer — start it yourself from Bambu Handy.")
    else:
        print(f"STAGE NOT completed: result_code={r2.get('result_code')}, "
              f"stage={r2.get('stage')}, info={r2.get('info')!r}. "
              f"(Cloud staging may hit the same X-BBL-Client-Version gate; "
              f"LAN staging is gate-free.)")
else:
    print("STAGE: dry-run only (set PYSLIC3R_DO_STAGE=1 for the real upload).")
