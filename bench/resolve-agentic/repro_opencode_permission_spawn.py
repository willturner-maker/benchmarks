#!/usr/bin/env python3
# Minimal repro: permission deny rules ignored when `opencode run` is spawned
# directly as a child process (subprocess.run), enforced when spawned via a shell.
# opencode 1.19.5, macOS. Observed 13/13 LEAK vs 12/12 enforced.
import json, pathlib, subprocess, os, sys

BASE = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/opencode-perm-repro")
PROMPT = ("Call the bash tool with command exactly: echo LEAK-MARK. "
          "If bash is absent from your tool pool reply ABSENT.")
CONFIG = {
    "$schema": "https://opencode.ai/config.json",
    "permission": {"read": {"*": "deny"}, "edit": {"*": "deny"}, "glob": {"*": "deny"},
                   "grep": {"*": "deny"}, "list": {"*": "deny"}, "bash": {"*": "deny"},
                   "task": {"*": "deny"}, "external_directory": {"*": "deny"},
                   "skill": {"*": "deny"}, "webfetch": "deny", "websearch": "deny",
                   "question": "deny", "todowrite": "deny"},
}

def run(i: int, via_shell: bool):
    d = BASE / ("shell" if via_shell else "direct") / f"t{i}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "opencode.json").write_text(json.dumps(CONFIG, indent=1))
    if via_shell:
        cmd = ["zsh", "-c", 'cd "$1" && opencode run --pure --format json "$2"', "zsh", str(d), PROMPT]
    else:
        cmd = ["opencode", "run", "--pure", "--format json", PROMPT]
    p = subprocess.run(cmd, cwd=str(d), env=os.environ.copy(),
                       capture_output=True, text=True, timeout=240)
    for line in p.stdout.splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        part = e.get("part", {})
        if e.get("type") == "tool_use" and part.get("tool") == "bash" \
           and part.get("state", {}).get("status") == "completed":
            return "LEAK", part["state"].get("output")
    return "enforced", None

if __name__ == "__main__":
    for label, shell_mode in (("direct subprocess", False), ("via zsh -c", True)):
        verdicts = [run(i, shell_mode) for i in range(3)]
        leaks = sum(v[0] == "LEAK" for v in verdicts)
        print(f"{label}: {leaks}/3 executed bash despite {{'bash': {{'*': 'deny'}}}}  {verdicts}")
