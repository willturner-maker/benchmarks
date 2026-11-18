#!/usr/bin/env python3
"""Tier 2 measurement — MCP tool-name mangling in the Resolve agentic waves.

Why: across the 2026-11-17h passes, ~57 and ~58 errored calls per pass were the harness answering
`No tool named "<mangled>" is currently available.` The model reaches for names like
`davinci-resolve-media_pool`, `davinci-resolve-media-pool-probe_media_pool` or
`davinci-resolve_project_manager_snapshot` — three different wrong guesses at the SAME convention
(server-tool, separated by "_" in OpenCode 2.3.0). It cost nothing in 20 of 21 trials (the model
recovers in 1-2 calls) and everything in one (pass-1 T2r1: nine attempts, zero completed calls,
task failed). This script quantifies the phenomenon so a fix can be measured rather than asserted.

It reports per trial:
  attempts            how many mangled-name calls the trial made
  distinct_names      how many different wrong spellings it invented
  recovery            calls between the first mangled attempt and the first completed call
                      (None = never recovered, i.e. the trial never reached the surface)
  wasted_ms           harness time burned on mangled attempts
  intended            best guess at the tool it meant (nearest name among the tools that trial
                      DID complete, after stripping separators)
Plus wave-level totals and the error text shape (the harness message does NOT suggest a name —
it says "Please use a tool from the available tool list", which is why a bad guess can repeat).

Usage: python3 mangle_analysis.py --wave results/baseline-2026-11-17h \
           --also results/baseline-2026-11-17h2 --out results/<wave>/mangle-analysis.json
"""
import argparse, collections, json, pathlib, re

NO_TOOL = "No tool named"


def events(p):
    out = []
    for ln in pathlib.Path(p).read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return out


def norm(name):
    """Collapse the separators the model confuses, so intended-vs-attempted can be compared."""
    return re.sub(r"[-_.]", "", str(name or "")).lower()


def scan_wave(wdir):
    per, tot = {}, collections.Counter()
    shapes = collections.Counter()
    for ev in sorted(pathlib.Path(wdir).glob("sessions/*/events.json")):
        task = ev.parent.name
        seq = []
        for e in events(ev):
            if e.get("type") != "tool_use":
                continue
            part = e.get("part") or {}
            st = part.get("state") or {}
            seq.append((str(part.get("tool") or ""), st.get("status"), st))
        completed_norm = {norm(n) for n, s, _ in seq if s == "completed"}
        attempts = [(i, n, st) for i, (n, s, st) in enumerate(seq)
                    if s == "error" and NO_TOOL in str(st.get("error") or "")]
        first_ok = next((i for i, (n, s, _) in enumerate(seq) if s == "completed"), None)
        first_bad = attempts[0][0] if attempts else None
        recovery = None
        if attempts:
            after = [i for i, (n, s, _) in enumerate(seq) if s == "completed" and i > first_bad]
            recovery = (min(after) - first_bad) if after else None
        wasted = sum(int(((st.get("time") or {}).get("end", 0)) -
                         ((st.get("time") or {}).get("start", 0))) for _, _, st in attempts)
        intended = collections.Counter()
        for _, n, _ in attempts:
            want = norm(n)
            cands = [c for c in completed_norm if c and (c in want or want in c)]
            for c in cands[:1]:
                intended[c] += 1
        rec = {"attempts": len(attempts),
               "distinct_names": len({n for _, n, _ in attempts}),
               "names": sorted({n for _, n, _ in attempts}),
               "first_attempt_index": first_bad, "calls_before_first_success": first_ok,
               "recovery_calls": recovery, "wasted_ms": wasted,
               "intended_map": dict(intended)}
        per[task] = rec
        tot["attempts"] += len(attempts)
        tot["distinct_names"] += rec["distinct_names"]
        tot["trials_with_attempts"] += 1 if attempts else 0
        tot["trials_never_recovering"] += 1 if (attempts and recovery is None) else 0
        tot["wasted_ms"] += wasted
        for _, n, st in attempts:
            shapes[re.sub(r'No tool named ".*?"', 'No tool named "<X>"',
                          str(st.get("error") or ""))] += 1
    return per, dict(tot), dict(shapes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", required=True)
    ap.add_argument("--also", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = {}
    for w in [a.wave] + [x for x in a.also.split(",") if x]:
        per, tot, shapes = scan_wave(pathlib.Path(w))
        trials = len(per)
        out[w] = {"trials": trials, "totals": tot,
                  "mean_attempts_per_trial": round(tot["attempts"] / trials, 2) if trials else 0,
                  "error_message_shapes": shapes,
                  "worst_trials": sorted((r for r in per.values() if r["attempts"]),
                                         key=lambda r: -r["attempts"])[:5],
                  "per_trial": per}
        print(f"{w}: trials={trials} attempts={tot['attempts']} "
              f"trials_with_attempts={tot['trials_with_attempts']} "
              f"never_recovered={tot['trials_never_recovering']} "
              f"wasted_ms={tot['wasted_ms']}")
        for shape in shapes:
            print("   shape:", shape[:120])
    pathlib.Path(a.out).write_text(json.dumps(out, indent=1))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
