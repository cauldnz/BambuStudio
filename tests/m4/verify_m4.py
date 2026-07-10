"""M4 cloud device plane assertions (READ-ONLY), run in-process by the
self-test on the wx main thread.

What this milestone-partial proves without a bound printer:
  - the signed network plugin loads headless (device.available), and
  - the device API is reachable — login state, account-bound printer
    enumeration (empty is valid), selection/status plumbing.

Login-token *persistence* to a headless datadir copy is REPORTED, not
asserted (it depends on the running GUI having flushed the token). send /
live status / camera are deferred until a printer is bound to the account.
"""
import os
import pyslic3r

dev = pyslic3r.app.device

print("M4 diag: device.available   =", dev.available)
print("M4 diag: is_logged_in       =", dev.is_logged_in)
print("M4 diag: user_id            =", dev.user_id)
print("M4 diag: user_name          =", repr(dev.user_name))

# Fetch the account's bound printers from the cloud (a fresh instance hasn't).
if dev.is_logged_in:
    n = dev.refresh()
    print("M4 diag: refresh -> cloud reports", n, "printer(s)")

printers = dev.printers()
print("M4 diag: bound printers      =",
      [(p.dev_id, p.name, p.online) for p in printers])

# If a printer is bound, exercise select + LIVE status telemetry (READ-ONLY).
if printers:
    p = printers[0]
    dev.select(p.dev_id)
    print("M4 diag: selected            =", (dev.selected.dev_id if dev.selected else None))
    # wait>0: force subscribe + pushall + wait for the printer's status push.
    st = dev.status(wait=25)
    print("M4 diag: connected           =", st.get("connected"),
          "awaiting_push =", st.get("awaiting_push"))
    print("M4 diag: print_status        =", repr(st.get("print_status")),
          "stage =", repr(st.get("stage")))
    print("M4 diag: bed_temp            =", st.get("bed_temp"), "/", st.get("bed_temp_target"))
    print("M4 diag: nozzles             =", st.get("nozzles"))
    print("M4 diag: chamber             =", st.get("chamber_temp"), "/", st.get("chamber_temp_target"))
    print("M4 diag: hms                 =", st.get("hms"))
    # Telemetry sanity: if the printer is online and we got a push, we should
    # have real ambient temperatures (a bed reading > 0).
    if p.online and not st.get("awaiting_push", True):
        assert st.get("bed_temp", 0) > 0, f"push received but no bed temp: {st}"
        print("M4 diag: LIVE TELEMETRY OK (received status push from the printer)")
else:
    sel = dev.selected
    print("M4 diag: selected            =", (sel.dev_id if sel else None))
    print("M4 diag: status              =", dev.status())

# --- hard asserts: the device-plane INFRASTRUCTURE is reachable -----------
assert dev.available, "network plugin not available (libbambu_networking.so not loaded)"
assert isinstance(printers, list), "device.printers() did not return a list"
# selection/status plumbing must not throw and must be well-typed:
sel = dev.selected
assert sel is None or isinstance(sel.dev_id, str), "selected has bad dev_id"
st = dev.status()
assert st is None or isinstance(st, dict), "status() not None-or-dict"
# with a bound printer we should have enumerated at least one:
if dev.is_logged_in and len(printers) > 0:
    assert all(isinstance(p.dev_id, str) and p.dev_id for p in printers), "bad printer dev_id"

# --- reported finding: did the login persist to this (headless) datadir? ---
expect = os.environ.get("PYSLIC3R_M4_EXPECT_USER", "")
if dev.is_logged_in:
    assert dev.user_id, "logged in but no user_id"
    if expect:
        assert dev.user_id == expect, \
            f"logged-in user {dev.user_id!r} != expected {expect!r}"
    print(f"M4 verify OK: device plane up, LOGGED IN as {dev.user_id} "
          f"({dev.user_name!r}), {len(printers)} bound printer(s)")
else:
    # Not a failure of this milestone-partial: the plugin loaded and the API
    # is reachable. Login didn't persist to the headless copy — a deployment
    # finding (see M4-RESULT). The write half needs a live logged-in session.
    print(f"M4 verify OK: device plane up (plugin loaded, API reachable), "
          f"NOT logged in on this headless datadir "
          f"(login-persistence finding — see M4-RESULT)")
