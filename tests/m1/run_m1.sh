#!/bin/bash
# M1 self-verify harness (read-only object model).
# Runs the built app offscreen under Xvfb, imports the two-cube fixtures, then
# runs the M0 marshalling checks PLUS the M1 read-model asserts (verify_m1.py),
# and turns the result into an exit code. Usage: tests/m1/run_m1.sh [binary]
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${1:-${ROOT}/build/src/bambu-studio}"
FIXDIR="${ROOT}/tests/fixtures"
RESULT="${PYSLIC3R_M0_RESULT:-${ROOT}/M1-RESULT.md}"
RUNLOG="${ROOT}/tests/m1/m1-run.log"

# A datadir that has already been through first-run (real app config present),
# so no config-wizard modal fires. Fall back to a throwaway if absent.
SEED="${PYSLIC3R_M0_SEED:-${HOME}/m0-seed-datadir}"
DATADIR="$(mktemp -d /tmp/pyslic3r-m1-datadir.XXXXXX)"
if [ -d "$SEED" ]; then cp -rT "$SEED" "$DATADIR"; fi

[ -x "$BIN" ] || { echo "FAIL: binary not found/executable: $BIN"; exit 2; }
[ -f "${FIXDIR}/cube_a.stl" ] || python3 "${FIXDIR}/gen_two_object_stls.py" "$FIXDIR"

rm -f "$RESULT"
export PYSLIC3R_M0_TEST=1
export PYSLIC3R_M0_RESULT="$RESULT"
export PYSLIC3R_M0_FIXTURES="${FIXDIR}/cube_a.stl;${FIXDIR}/cube_b.stl"
export PYSLIC3R_M0_EXPECT_OBJECTS=2
export PYSLIC3R_TEST_LABEL=M1
export PYSLIC3R_M1_TEST=1
export PYSLIC3R_M1_SCRIPT="${ROOT}/tests/m1/verify_m1.py"

if [ -z "${SSL_CERT_FILE:-}" ] && [ -f /etc/ssl/certs/ca-certificates.crt ]; then
    export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
fi

DBUS_WRAP=""
command -v dbus-run-session >/dev/null && DBUS_WRAP="dbus-run-session --"

echo "M1: launching offscreen (datadir=$DATADIR, fixtures via env)"
start_s=$SECONDS
timeout --signal=TERM --kill-after=30 300 \
    $DBUS_WRAP xvfb-run --auto-servernum "$BIN" --datadir "$DATADIR" \
    > "$RUNLOG" 2>&1
rc=$?
echo "M1: app exited rc=$rc after $((SECONDS - start_s))s"

if [ -f "$RESULT" ] && grep -q "^RESULT: PASS" "$RESULT" && [ "$rc" -eq 0 ]; then
    echo "M1: PASS"
    grep -E "^- (PASS|FAIL)|^\| " "$RESULT" || true
    exit 0
fi

echo "M1: FAIL (rc=$rc, result file: $([ -f "$RESULT" ] && echo present || echo missing))"
echo "--- last 40 lines of $RUNLOG ---"
tail -40 "$RUNLOG"
exit 1
