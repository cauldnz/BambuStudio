#!/bin/bash
# SEND self-verify harness: slice the loaded fixture, fetch the camera URL, and
# DRY-RUN the send (export + prepare, NO dispatch) against the logged-in device
# datadir. Never dispatches a real print.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${1:-${ROOT}/build/src/bambu-studio}"
FIXDIR="${ROOT}/tests/fixtures"
RESULT="${PYSLIC3R_M0_RESULT:-${ROOT}/SEND-RESULT.md}"
RUNLOG="${ROOT}/tests/m4/send-run.log"

SEED="${PYSLIC3R_SEND_SEED:-${HOME}/device-datadir}"   # logged-in + installed printer
DATADIR="$(mktemp -d /tmp/pyslic3r-send-datadir.XXXXXX)"
if [ -d "$SEED" ]; then cp -rT "$SEED" "$DATADIR"; fi

[ -x "$BIN" ] || { echo "FAIL: binary not found: $BIN"; exit 2; }
[ -f "${FIXDIR}/cube_a.stl" ] || python3 "${FIXDIR}/gen_two_object_stls.py" "$FIXDIR"

rm -f "$RESULT"
export PYSLIC3R_M0_TEST=1
export PYSLIC3R_M0_RESULT="$RESULT"
export PYSLIC3R_M0_FIXTURES="${FIXDIR}/cube_a.stl;${FIXDIR}/cube_b.stl"
export PYSLIC3R_M0_EXPECT_OBJECTS=2
export PYSLIC3R_TEST_LABEL=SEND
export PYSLIC3R_SEND_TEST=1
export PYSLIC3R_SEND_SCRIPT="${ROOT}/tests/m4/verify_send.py"
export PYTHONUNBUFFERED=1   # flush verify_send diagnostics live

if [ -z "${SSL_CERT_FILE:-}" ] && [ -f /etc/ssl/certs/ca-certificates.crt ]; then
    export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
fi
DBUS_WRAP=""
command -v dbus-run-session >/dev/null && DBUS_WRAP="dbus-run-session --"

echo "SEND: launching offscreen (datadir=$DATADIR)"
start_s=$SECONDS
timeout --signal=TERM --kill-after=30 360 \
    $DBUS_WRAP xvfb-run --auto-servernum "$BIN" --datadir "$DATADIR" \
    > "$RUNLOG" 2>&1
rc=$?
echo "SEND: app exited rc=$rc after $((SECONDS - start_s))s"

if [ -f "$RESULT" ] && grep -q "^RESULT: PASS" "$RESULT" && [ "$rc" -eq 0 ]; then
    echo "SEND: PASS"
    grep -E "^- (PASS|FAIL)" "$RESULT" || true
    exit 0
fi

echo "SEND: FAIL (rc=$rc)"
echo "--- SEND diag + tail ---"
grep -aE "SEND diag|SEND verify|SEND:|slice failed|asserts failed" "$RUNLOG" | grep -aviE "dbus|webkit" | tail -20
exit 1
