#!/bin/bash
# M3 self-verify harness (slicing). Runs the app offscreen, imports the
# two-cube fixtures, then runs M0 marshalling + M1 read + M2 mutation + M3
# slicing asserts (verify_m3.py), and turns the result into an exit code.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${1:-${ROOT}/build/src/bambu-studio}"
FIXDIR="${ROOT}/tests/fixtures"
RESULT="${PYSLIC3R_M0_RESULT:-${ROOT}/M3-RESULT.md}"
RUNLOG="${ROOT}/tests/m3/m3-run.log"

SEED="${PYSLIC3R_M0_SEED:-${HOME}/m0-seed-datadir}"
DATADIR="$(mktemp -d /tmp/pyslic3r-m3-datadir.XXXXXX)"
if [ -d "$SEED" ]; then cp -rT "$SEED" "$DATADIR"; fi

[ -x "$BIN" ] || { echo "FAIL: binary not found/executable: $BIN"; exit 2; }
[ -f "${FIXDIR}/cube_a.stl" ] || python3 "${FIXDIR}/gen_two_object_stls.py" "$FIXDIR"

rm -f "$RESULT"
export PYSLIC3R_M0_TEST=1
export PYSLIC3R_M0_RESULT="$RESULT"
export PYSLIC3R_M0_FIXTURES="${FIXDIR}/cube_a.stl;${FIXDIR}/cube_b.stl"
export PYSLIC3R_M0_EXPECT_OBJECTS=2
export PYSLIC3R_TEST_LABEL=M3
export PYSLIC3R_M1_TEST=1
export PYSLIC3R_M1_SCRIPT="${ROOT}/tests/m1/verify_m1.py"
export PYSLIC3R_M2_TEST=1
export PYSLIC3R_M2_SCRIPT="${ROOT}/tests/m2/verify_m2.py"
export PYSLIC3R_M2_ADD_FILE="${FIXDIR}/cube_a.stl"
export PYSLIC3R_M3_TEST=1
export PYSLIC3R_M3_SCRIPT="${ROOT}/tests/m3/verify_m3.py"
export PYSLIC3R_M3_PRINTER="Bambu Lab X1 Carbon 0.4 nozzle"

if [ -z "${SSL_CERT_FILE:-}" ] && [ -f /etc/ssl/certs/ca-certificates.crt ]; then
    export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
fi

DBUS_WRAP=""
command -v dbus-run-session >/dev/null && DBUS_WRAP="dbus-run-session --"

echo "M3: launching offscreen (datadir=$DATADIR)"
start_s=$SECONDS
# Slicing takes real wall-clock; allow the whole run up to 8 min.
timeout --signal=TERM --kill-after=30 480 \
    $DBUS_WRAP xvfb-run --auto-servernum "$BIN" --datadir "$DATADIR" \
    > "$RUNLOG" 2>&1
rc=$?
echo "M3: app exited rc=$rc after $((SECONDS - start_s))s"

if [ -f "$RESULT" ] && grep -q "^RESULT: PASS" "$RESULT" && [ "$rc" -eq 0 ]; then
    echo "M3: PASS"
    grep -E "^- (PASS|FAIL)|^\| " "$RESULT" || true
    exit 0
fi

echo "M3: FAIL (rc=$rc, result file: $([ -f "$RESULT" ] && echo present || echo missing))"
echo "--- last 50 lines of $RUNLOG ---"
tail -50 "$RUNLOG"
exit 1
