"""P2S REAL PRINT — dispatches a physical print. Only run with explicit human
approval of THIS specific print. Slices the 20 mm cube (P2S presets),
establishes the cloud connection, then send(dry_run=False) to start the print,
and polls status so we can see it begin (also tells us if the cloud gates our
unofficial build with update_studio).
"""
import pyslic3r

app = pyslic3r.app
doc = app.active_document

doc.plates.arrange(wait=True)
res = doc.slice().wait(timeout=300)
assert res.success, f"slice failed: {res.error}"
print(f"P2S PRINT: sliced {res.layer_count} layers, ~{res.print_time_s // 60} min")

dev = app.device
dev.refresh()
printers = dev.printers()
assert printers, "no bound printer"
dev.select(printers[0].dev_id)

# Establish the cloud connection first (sets connection_type='cloud').
st = dev.status(wait=25)
print("P2S PRINT: pre-send connected =", st.get("connected"),
      "print_status =", repr(st.get("print_status")))

# === REAL DISPATCH ===
print("P2S PRINT: DISPATCHING real print to the P2S ...")
r = dev.send(dry_run=False, use_ams=True, ams_mapping="[0]",
             project_name="pyslic3r-p2s-cube")
print("P2S PRINT: send result =", r)

if r.get("dispatched"):
    print("P2S PRINT: DISPATCHED OK — the cloud accepted the print. Polling status:")
    for _ in range(8):
        s = dev.status(wait=8)
        print("P2S PRINT: status =",
              {k: s.get(k) for k in ("print_status", "progress",
                                     "current_layer", "total_layers", "stage")})
    print("P2S PRINT DONE: dispatched; monitor the rest on Bambu Handy.")
else:
    print(f"P2S PRINT: NOT dispatched — result_code={r.get('result_code')}, "
          f"stage={r.get('stage')}, info={r.get('info')!r}. "
          f"Likely the unofficial-build cloud gate (update_studio).")
