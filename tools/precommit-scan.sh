#!/usr/bin/env bash
# precommit-scan.sh — refuse to commit local-machine paths, camera filenames,
# credentials, or named projects/clients into a repo that is (or will be) public.
#
#   bash tools/precommit-scan.sh              # scan what is staged (pre-commit mode)
#   bash tools/precommit-scan.sh --all        # scan every tracked file at HEAD (audit)
#   bash tools/precommit-scan.sh --install    # wire itself up as .git/hooks/pre-commit
#
# Repo-local deny terms (NEVER committed, so they can name the things to keep out):
#   $(git rev-parse --git-dir)/info/precommit-terms   — one substring per line, # = comment
# Known-good matches to ignore:
#   tools/precommit-allowlist                         — one regex per line, committed
#
# Escape hatch: PRECOMMIT_SCAN_SKIP=1 git commit ...  (prints a loud warning; use it
# only when the match is genuinely meant to be public, and say why in the commit msg).

set -uo pipefail

git rev-parse --git-dir >/dev/null 2>&1 || { echo "not a git repo"; exit 2; }
GITDIR=$(git rev-parse --git-dir)
TERMS="$GITDIR/info/precommit-terms"
ALLOWLIST="tools/precommit-allowlist"

# name|regex   (split on the FIRST pipe; the regex may contain pipes)
rules() {
  cat <<'RULES'
home-path|/(Users|home)/[A-Za-z0-9._-]+/
named-volume|/Volumes/[A-Za-z0-9._-]+
camera-filename|\b[A-Z][0-9]{5,}\.(mov|mp4|m4v)
credential-assignment|(api[_-]?key|apikey|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd)[[:space:]]*[:=][[:space:]]*["'`]?[A-Za-z0-9_./+:-]{12,}
key-format|\b(sk-[A-Za-z0-9]{12,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{20,}|AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,})
private-key-block|-----BEGIN [A-Z ]*PRIVATE KEY-----
secret-file-path|(\.claude\.json|brave-keys\.json|\.netrc|\.aws/credentials|\.ssh/id_[a-z0-9]+)
email|\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b
RULES
}

allow_regexes=()
if [[ -f "$ALLOWLIST" ]]; then
  while IFS= read -r line; do
    [[ -z "$line" || "$line" == \#* ]] && continue
    allow_regexes+=("$line")
  done < "$ALLOWLIST"
fi
allowed() {  # $1 = matched line
  local a
  for a in "${allow_regexes[@]+"${allow_regexes[@]}"}"; do
    if printf '%s' "$1" | grep -qEi -- "$a"; then return 0; fi
  done
  return 1
}

findings=0
report() { # file rule lineno content
  if allowed "$3"; then return; fi
  printf '  %s  [%s]  %s\n' "$1" "$2" "${3:0:160}"
  findings=$((findings + 1))
}

if [[ "${1:-}" == "--install" ]]; then
  hook="$GITDIR/hooks/pre-commit"
  cp "$(git rev-parse --show-toplevel)/tools/precommit-scan.sh" "$hook"
  chmod +x "$hook"
  echo "installed: $hook"
  echo "deny terms (untracked): $TERMS"
  exit 0
fi

# What to scan: staged paths, or all tracked paths with --all.
paths=()
if [[ "${1:-}" == "--all" ]]; then
  while IFS= read -r f; do paths+=("$f"); done < <(git ls-files)
else
  while IFS= read -r -d '' f; do paths+=("$f"); done \
    < <(git diff --cached -z --diff-filter=ACM --name-only)
fi
(( ${#paths[@]} )) && echo "precommit-scan: ${#paths[@]} file(s), $(wc -l < <(rules)) rules$(
  [[ -f "$TERMS" ]] && echo ", $(grep -cvE '^\s*(#|$)' "$TERMS") deny term(s)")"

for f in "${paths[@]+"${paths[@]}"}"; do
  # 1. the path itself
  while IFS='|' read -r name regex; do
    [[ -z "$name" ]] && continue
    if hit=$(printf '%s' "$f" | grep -Ein -- "$regex"); then report "$f" "$name" "$hit"
    fi
  done < <(rules)

  # 2. the content (staged blob / HEAD blob), binary files skipped by grep -I
  if [[ "${1:-}" == "--all" ]]; then blob=$(git show "HEAD:$f" 2>/dev/null); else blob=$(git show ":$f" 2>/dev/null); fi
  while IFS='|' read -r name regex; do
    [[ -z "$name" ]] && continue
    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      lineno=${line%%:*}
      report "$f:$lineno" "$name" "${line#*:}"
    done < <(printf '%s\n' "$blob" | grep -InEi -- "$regex" 2>/dev/null || true)
  done < <(rules)

  # 3. repo-local deny terms (project / client / event names)
  if [[ -f "$TERMS" ]]; then
    while IFS= read -r term; do
      [[ -z "$term" || "$term" == \#* ]] && continue
      while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        lineno=${line%%:*}
        report "$f:$lineno" "deny-term:$term" "${line#*:}"
      done < <(printf '%s\n' "$blob" | grep -InF -- "$term" 2>/dev/null || true)
    done < "$TERMS"
  fi
done

if (( findings )); then
  cat <<EOF

BLOCKED: $findings finding(s) that would become public.

Fix by one of:
  • remove/rewrite the value (a property description is usually better than a name —
    "8128x4288 HEVC Main 10, 56 min" documents more than a filename ever did),
  • add a regex to $ALLOWLIST if it is genuinely meant to be public,
  • or PRECOMMIT_SCAN_SKIP=1 git commit ... (say why in the message).
EOF
  exit 1
fi
[[ "${#paths[@]}" -gt 0 ]] && echo "precommit-scan: clean"
exit 0
