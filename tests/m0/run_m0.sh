#!/bin/bash
# M0 self-verify harness (LAUNCH.md pass/fail gate).
# Runs the built app offscreen under Xvfb against the two-object fixture,
# waits for the in-app self-test to write its result, and turns that into
# an exit code. Usage: tests/m0/run_m0.sh [path-to-binary]
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${1:-${ROOT}/build/src/bambu-studio}"
FIXDIR="${ROOT}/tests/fixtures"
RESULT="${PYSLIC3R_M0_RESULT:-${ROOT}/M0-RESULT.md}"
RUNLOG="${ROOT}/tests/m0/m0-run.log"

# A datadir that has already been through first-run (real app config present),
# so no config-wizard modal fires. Built once by seed_datadir.sh; fall back to
# a throwaway if absent (will hit the wizard, but keeps the script runnable).
SEED="${PYSLIC3R_M0_SEED:-${HOME}/m0-seed-datadir}"
DATADIR="$(mktemp -d /tmp/pyslic3r-m0-datadir.XXXXXX)"
if [ -d "$SEED" ]; then cp -rT "$SEED" "$DATADIR"; fi

[ -x "$BIN" ] || { echo "FAIL: binary not found/executable: $BIN"; exit 2; }
[ -f "${FIXDIR}/cube_a.stl" ] || python3 "${FIXDIR}/gen_two_object_stls.py" "$FIXDIR"

rm -f "$RESULT"
export PYSLIC3R_M0_TEST=1
export PYSLIC3R_M0_RESULT="$RESULT"
export PYSLIC3R_M0_FIXTURES="${FIXDIR}/cube_a.stl;${FIXDIR}/cube_b.stl"
export PYSLIC3R_M0_EXPECT_OBJECTS=2

# Static-OpenSSL builds can't find the distro CA bundle and pop a modal
# confirmation dialog during on_init_inner — fatal headless. Pointing
# SSL_CERT_FILE at the system bundle skips that code path entirely.
if [ -z "${SSL_CERT_FILE:-}" ] && [ -f /etc/ssl/certs/ca-certificates.crt ]; then
    export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
fi

# WebKit (first-run wizard, web panels) needs a session bus; without one it
# can wedge the GUI thread under Xvfb.
DBUS_WRAP=""
command -v dbus-run-session >/dev/null && DBUS_WRAP="dbus-run-session --"

echo "M0: launching offscreen (datadir=$DATADIR, fixtures via env)"
start_s=$SECONDS
# No file on argv: the self-test imports the fixtures itself via the
# non-interactive Plater path once the app is up.
timeout --signal=TERM --kill-after=30 300 \
    $DBUS_WRAP xvfb-run --auto-servernum "$BIN" --datadir "$DATADIR" \
    > "$RUNLOG" 2>&1
rc=$?
echo "M0: app exited rc=$rc after $((SECONDS - start_s))s"

# PASS requires: the self-test says PASS *and* the app exited cleanly
# (clean interpreter finalize is part of the gate — a hang trips `timeout`
# giving rc=124, a crash gives a signal rc).
if [ -f "$RESULT" ] && grep -q "^RESULT: PASS" "$RESULT" && [ "$rc" -eq 0 ]; then
    echo "M0: PASS"
    grep -E "^\| " "$RESULT" || true
    exit 0
fi

echo "M0: FAIL (rc=$rc, result file: $([ -f "$RESULT" ] && echo present || echo missing))"
echo "--- last 40 lines of $RUNLOG ---"
tail -40 "$RUNLOG"
exit 1
