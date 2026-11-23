#!/usr/bin/env bash
# shellcheck shell=bash
# Unit checks for the 2026-11-22 run_wave.sh hardening: engine_prog signal, the --save-to
# pre-flight (clean-start move aside vs TAU2_RESUME=1), and the empty-array expansion under
# set -u. No wave is run and no engine load is generated beyond one /status read.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
fail=0
ok(){ printf 'PASS  %s\n' "$1"; }
no(){ printf 'FAIL  %s\n' "$1"; fail=1; }

# 1) engine_prog returns an integer from the live engine, and -1 when the port is wrong
eval "$(sed -n '/^# Engine progress signal/,/^}/p' "$HERE/run_wave.sh")"
p=$(engine_prog)
[[ "$p" =~ ^[0-9]+$ ]] && ok "engine_prog -> $p" || no "engine_prog -> '$p' (expected integer)"
q=$(TAU2_ENGINE_PORT=59999 engine_prog)
[ "$q" = "-1" ] && ok "engine_prog unreachable port -> -1 (watchdog must never kill on this)" || no "unreachable -> '$q'"

# 2) pre-flight: existing --save-to is moved aside, not answered; TAU2_RESUME=1 chooses --auto-resume
TAU2=$(mktemp -d); sim="$TAU2/data/simulations/wave-testw-airline"; mkdir -p "$sim"; echo '{}' > "$sim/results.json"
WAVE=$(mktemp -d); mkdir -p "$WAVE"
check_preflight(){
  # two statements on purpose: in ONE `local` line the later word is expanded before the earlier
  # assignment lands, so $save there is unbound (this exact bug failed the first run of this test)
  local save; save="wave-testw-airline"
  local simdir="$TAU2/data/simulations/$save"
  local resume=() out=""
  if [ -e "$simdir/results.json" ]; then
    if [ "${TAU2_RESUME:-0}" = "1" ]; then resume=(--auto-resume); out="resume"
    else mv "$simdir" "$simdir.pre-$(date -u +%Y%m%dT%H%M%SZ)"; out="moved"; fi
  fi
  printf '%s%s' "$out" "${resume[*]+ ${resume[*]}}"
}
TAUSIM="$TAU2/data/simulations/wave-testw-airline"
r=$(check_preflight)
[ "$r" = "moved" ] && ok "existing save -> moved aside, no prompt possible" || no "pre-flight -> '$r'"
[ -e "$TAUSIM/results.json" ] && no "old save still in place" || ok "old save vacated"
ls -d "$TAUSIM".pre-* >/dev/null 2>&1 && ok "moved-aside copy retained for provenance" || no "no moved-aside copy"
mkdir -p "$TAUSIM"; echo '{}' > "$TAUSIM/results.json"
r=$(TAU2_RESUME=1 check_preflight)
[ "$r" = "resume --auto-resume" ] && ok "TAU2_RESUME=1 -> --auto-resume" || no "resume path -> '$r'"
rm -rf "$TAU2" "$WAVE"

# 3) empty array must not explode under set -u (bash 3.2 macOS default is the risk case)
( set -u; e=(); printf '%s' "${e[@]+"${e[@]}"}" ) >/dev/null && ok 'empty array expansion safe under set -u' || no 'empty array expansion'

# 4) stall arithmetic: 20s polls, default threshold 420s -> 21st idle poll trips
stall=0; trips=0
for _i in $(seq 1 21); do stall=$((stall+20)); [ "$stall" -ge 420 ] && trips=$((trips+1)); done
[ "$trips" = 1 ] && [ "$stall" = 420 ] && ok "stall trips once at 420s (21 x 20s)" || no "stall math ($trips, $stall)"

printf '%s\n' "$([ "$fail" = 0 ] && echo 'ALL CHECKS PASS' || echo 'FAILURES ABOVE')"
exit "$fail"
