#!/bin/bash
# Test the pyslic3r script runner: launch the app offscreen with a user script
# via PYSLIC3R_SCRIPT (batch mode, PYSLIC3R_SCRIPT_EXIT=1) and check it ran and
# exited cleanly. Deliberately does NOT set PYSLIC3R_M0_TEST — this exercises
# the general script-runner path, not the self-test.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${1:-${ROOT}/build/src/bambu-studio}"
FIXDIR="${ROOT}/tests/fixtures"
RUNLOG="${ROOT}/tests/runner/runner-run.log"

SEED="${PYSLIC3R_RUNNER_SEED:-${HOME}/m0-seed-datadir}"   # installed printer -> no wizard
DATADIR="$(mktemp -d /tmp/pyslic3r-runner-datadir.XXXXXX)"
if [ -d "$SEED" ]; then cp -rT "$SEED" "$DATADIR"; fi

[ -x "$BIN" ] || { echo "FAIL: binary not found/executable: $BIN"; exit 2; }
[ -f "${FIXDIR}/cube_a.stl" ] || python3 "${FIXDIR}/gen_two_object_stls.py" "$FIXDIR"

export PYSLIC3R_SCRIPT="${ROOT}/tests/runner/verify_runner.py"
export PYSLIC3R_SCRIPT_EXIT=1
export PYSLIC3R_RUNNER_STL="${FIXDIR}/cube_a.stl"

if [ -z "${SSL_CERT_FILE:-}" ] && [ -f /etc/ssl/certs/ca-certificates.crt ]; then
    export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
fi
DBUS_WRAP=""
command -v dbus-run-session >/dev/null && DBUS_WRAP="dbus-run-session --"

echo "runner: launching offscreen (script=$PYSLIC3R_SCRIPT)"
start_s=$SECONDS
timeout --signal=TERM --kill-after=30 200 \
    $DBUS_WRAP xvfb-run --auto-servernum "$BIN" --datadir "$DATADIR" \
    > "$RUNLOG" 2>&1
rc=$?
echo "runner: app exited rc=$rc after $((SECONDS - start_s))s"

# PASS: the runner reported OK, the script's own marker printed, clean exit.
if [ "$rc" -eq 0 ] \
   && grep -q "PYSLIC3R_SCRIPT: OK" "$RUNLOG" \
   && grep -q "RUNNER OK:" "$RUNLOG"; then
    echo "runner: PASS"
    grep -aE "RUNNER OK:|PYSLIC3R_SCRIPT:" "$RUNLOG" | tail -2
    exit 0
fi

echo "runner: FAIL (rc=$rc)"
echo "--- last 30 lines of $RUNLOG ---"
grep -avE "dbus|GStreamer|gvfs|VolumeMonitor|libEGL|Gtk-" "$RUNLOG" | tail -30
exit 1
