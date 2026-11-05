# Headless pyslic3r smoke test. bambu-studio.exe is a GUI-subsystem binary with no
# console stdout, so write the result to PYSLIC3R_VERIFY_OUT (a file) instead of
# printing. Run via PYSLIC3R_SCRIPT=<this> PYSLIC3R_SCRIPT_EXIT=1 bambu-studio.exe.
import os, traceback
out = os.environ.get("PYSLIC3R_VERIFY_OUT", "pyslic3r_smoke_out.txt")
with open(out, "w") as f:
    try:
        import pyslic3r
        app = pyslic3r.app
        f.write(f"OK {app.name} {app.version}\n")
        doc = app.active_document
        f.write(f"active_document={'present' if doc is not None else 'None'}\n")
        f.write("VERIFY_DONE\n")
    except Exception:
        f.write("EXCEPTION:\n" + traceback.format_exc())
