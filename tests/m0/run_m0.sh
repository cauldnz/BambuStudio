#!/bin/bash
# M0 self-verify harness (LAUNCH.md pass/fail gate).
# Runs the built app offscreen under Xvfb against the two-object fixture,
# waits for the in-app self-test to write its result, and turns that into
# an exit code. Usage: tests/m0/run_m0.sh [path-to-binary]
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${1:-${ROOT}/build/src/bambu-studio}"
FIXTURE="${ROOT}/tests/fixtures/two_object.3mf"
RESULT="${PYSLIC3R_M0_RESULT:-${ROOT}/M0-RESULT.md}"
RUNLOG="${ROOT}/tests/m0/m0-run.log"
DATADIR="$(mktemp -d /tmp/pyslic3r-m0-datadir.XXXXXX)"

[ -x "$BIN" ]     || { echo "FAIL: binary not found/executable: $BIN"; exit 2; }
[ -f "$FIXTURE" ] || python3 "${ROOT}/tests/fixtures/gen_two_object_3mf.py" "$FIXTURE"

rm -f "$RESULT"
export PYSLIC3R_M0_TEST=1
export PYSLIC3R_M0_RESULT="$RESULT"

echo "M0: launching offscreen (datadir=$DATADIR, fixture=$FIXTURE)"
start_s=$SECONDS
timeout --signal=TERM --kill-after=30 300 \
    xvfb-run --auto-servernum "$BIN" --datadir "$DATADIR" "$FIXTURE" \
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
