#!/bin/bash
# M4 self-verify harness (cloud device plane, read-only). Runs the app offscreen
# against a COPY of the logged-in device datadir (so the live GUI session, if
# any, is undisturbed), runs M0 marshalling + M4 device asserts, and turns the
# result into an exit code.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${1:-${ROOT}/build/src/bambu-studio}"
FIXDIR="${ROOT}/tests/fixtures"
RESULT="${PYSLIC3R_M0_RESULT:-${ROOT}/M4-RESULT.md}"
RUNLOG="${ROOT}/tests/m4/m4-run.log"

# The logged-in device datadir (has the network plugin + account session).
SEED="${PYSLIC3R_M4_SEED:-${HOME}/device-datadir}"
DATADIR="$(mktemp -d /tmp/pyslic3r-m4-datadir.XXXXXX)"
if [ -d "$SEED" ]; then cp -rT "$SEED" "$DATADIR"; fi

[ -x "$BIN" ] || { echo "FAIL: binary not found/executable: $BIN"; exit 2; }
[ -f "${FIXDIR}/cube_a.stl" ] || python3 "${FIXDIR}/gen_two_object_stls.py" "$FIXDIR"

rm -f "$RESULT"
export PYSLIC3R_M0_TEST=1
export PYSLIC3R_M0_RESULT="$RESULT"
export PYSLIC3R_M0_FIXTURES="${FIXDIR}/cube_a.stl;${FIXDIR}/cube_b.stl"
export PYSLIC3R_M0_EXPECT_OBJECTS=2
export PYSLIC3R_TEST_LABEL=M4
export PYSLIC3R_M4_TEST=1
export PYSLIC3R_M4_SCRIPT="${ROOT}/tests/m4/verify_m4.py"
export PYSLIC3R_M4_EXPECT_USER="${PYSLIC3R_M4_EXPECT_USER:-}"

if [ -z "${SSL_CERT_FILE:-}" ] && [ -f /etc/ssl/certs/ca-certificates.crt ]; then
    export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
fi

DBUS_WRAP=""
command -v dbus-run-session >/dev/null && DBUS_WRAP="dbus-run-session --"

echo "M4: launching offscreen (datadir=$DATADIR, from seed=$SEED)"
start_s=$SECONDS
timeout --signal=TERM --kill-after=30 300 \
    $DBUS_WRAP xvfb-run --auto-servernum "$BIN" --datadir "$DATADIR" \
    > "$RUNLOG" 2>&1
rc=$?
echo "M4: app exited rc=$rc after $((SECONDS - start_s))s"

if [ -f "$RESULT" ] && grep -q "^RESULT: PASS" "$RESULT" && [ "$rc" -eq 0 ]; then
    echo "M4: PASS"
    grep -E "^- (PASS|FAIL)" "$RESULT" || true
    exit 0
fi

echo "M4: FAIL (rc=$rc, result file: $([ -f "$RESULT" ] && echo present || echo missing))"
echo "--- last 40 lines of $RUNLOG ---"
tail -40 "$RUNLOG"
exit 1
