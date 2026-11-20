#!/usr/bin/env bash
# probe_seed_inert.sh — is the `seed` tau2 sends per trial doing anything to your engine?
#
# Why this exists: tau2 derives a different seed per trial (wave 2026-11-19a recorded 626729 for trial 0
# and 373753 for trial 1 under --seed 300) and puts it in the request body. That invites the explanation
# "the two trials differ because the user simulator was reseeded". On Splash 1.7.0 the answer is no: the
# greedy output is byte-identical under both seeds, so reseeding is not a flip mechanism here and a
# "same-seed replay" is not something this stack can offer.
#
# Run it on your own endpoint before you attribute any variance to the seed.
#
#   ./probe_seed_inert.sh [base_url] [model] [seed_a] [seed_b]
set -uo pipefail

BASE=${1:-http://127.0.0.1:8000/v1}
MODEL=${2:-'ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S'}
SEED_A=${3:-626729}
SEED_B=${4:-373753}
PROMPT='Name one number between 1 and 1000. Answer with the number only.'

call() {  # $1 = seed
  curl -s --max-time 120 "$BASE/chat/completions" -H 'content-type: application/json' -d "{
    \"model\": \"$MODEL\", \"temperature\": 0, \"seed\": $1, \"max_tokens\": 400,
    \"messages\": [{\"role\": \"user\", \"content\": \"$PROMPT\"}]}" |
    python3 -c '
import hashlib, json, sys
d = json.load(sys.stdin)
m = d["choices"][0]["message"]
text = (m.get("content") or "") + "|" + (m.get("reasoning_content") or "")
print(hashlib.sha1(text.encode()).hexdigest()[:16])'
}

echo "endpoint: $BASE"
echo "model:    $MODEL"
printf 'seed %s  sha1 %s\n' "$SEED_A" "$(call "$SEED_A")"
printf 'seed %s  sha1 %s\n' "$SEED_B" "$(call "$SEED_B")"
printf 'seed %s  sha1 %s\n' "$SEED_A" "$(call "$SEED_A")"
echo
echo "identical digests across both seeds => the engine ignores seed at temperature 0: reseeding is not a"
echo "source of variance, and a same-seed control run would not pin behaviour on this endpoint either."
echo "NOTE: run this unloaded. Under concurrency the answer can change for batching reasons, which is the"
echo "effect this probe is deliberately NOT testing."
