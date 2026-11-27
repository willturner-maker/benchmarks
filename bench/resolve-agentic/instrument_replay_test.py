#!/usr/bin/env python3
"""Instrument replay test: pins the driver's event parser, seal audit, pool
classifier and tool-pool manifest against RECORDED event streams — like
grader_selftest (58/58) but for the harness side.

Why: opencode 2.4.2 changed MCP tool-name joining from "server_tool" to
"server-tool" (plus concat forms with no join char) with no release-note
mention; the wave driver's probe/seal went blind and the wave discovered it
mid-run through seal-audit noise. Recorded events.json streams from both
naming eras (23e = 2.4.1 underscore era; 26b = 2.4.2 dash era) are on disk —
this test replays them (plus a synthetic three-form corpus) so any future
harness bump or driver edit regressions surface OFFLINE, before a wave touches
live Resolve.

Run from bench/resolve-agentic:  python3 instrument_replay_test.py
Wave results dirs are gitignored; missing eras are reported and skipped, so
this stays runnable on hosts without the raw waves."""
import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location(
    "drv", HERE / "wave_driver_f1f2_opencode_v2.py")
drv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drv)

fails = []
def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{(' — ' + detail) if detail else ''}")
    if not cond:
        fails.append(name)

# ---------- 1) synthetic corpus: the three observed name forms -------------
def evline(tool, status, err=None):
    part = {"tool": tool, "state": {"status": status}}
    if err:
        part["state"]["error"] = err
    return json.dumps({"type": "tool_use", "part": part})

SYN = "\n".join([
    evline("davinci-resolve-builtin_run_script", "completed"),          # underscore join
    evline("davinci-resolve-get_resolve_status", "completed"),          # dash join
    evline("davinci-resolveproject_manager", "completed"),              # concat form (2.4.2)
    evline("davinci-resolve-project_manager", "error",
           'No tool named "davinci-resolve-project_manager" is currently available.'),
    evline("project_manager", "error", 'No tool named "project_manager" is currently available.'),
    evline("some-other-server_tool_x", "completed"),                    # non-KEEP -> leak
])
sev = drv.parse_events(SYN)
check("synthetic parse: 6 tool events", len(sev["tool_uses"]) == 6)
leaks = drv.seal_audit(sev["tool_uses"])
check("synthetic seal_audit (current policy): KEEP names in all three forms allowed; "
      "bare name + non-KEEP leak",
      leaks == ["('project_manager', 'error')", "some-other-server_tool_x"], str(leaks))
old = drv.seal_audit(sev["tool_uses"], forms=("underscore",))
check("synthetic seal_audit (23e-era policy): dash/concat forms flagged as they were then",
      old == ["davinci-resolve-get_resolve_status", "davinci-resolveproject_manager",
              "('davinci-resolve-project_manager', 'error')", "('project_manager', 'error')",
              "some-other-server_tool_x"], str(old))
check("synthetic classify_pool: alive via completed dash-join",
      drv.classify_pool(SYN)["ok"] is True)

# pool-dead stream: only KEEP-named rejections with the dropout signature
DEAD = "\n".join(evline("davinci-resolve-project_manager", "error",
                        'No tool named "davinci-resolve-project_manager" is currently available.')
                 for _ in range(drv.RESOLVE_ERR_KILL))
pd = drv.classify_pool(DEAD)
check("synthetic classify_pool: dead after RESOLVE_ERR_KILL rejections",
      pd["dead"] is True and pd["ok"] is False)

# manifest forms over the synthetic corpus (fresh state)
drv.TOOL_FORMS.clear(); drv.TOOL_NAMES.clear()
drv.manifest_observe(sev["tool_uses"])
forms = drv.TOOL_FORMS
check("synthetic manifest: per-server form census correct",
      forms.get("davinci-resolve-builtin", {}).get("underscore") == 1
      and forms.get("davinci-resolve", {}).get("dash") == 1
      and forms.get("davinci-resolve", {}).get("concat") == 1,
      json.dumps(forms))

# ---------- 2) replay recorded waves: both naming eras ---------------------
# era -> seal naming policy IN FORCE at that wave's dispatch (replay must
# reproduce the recorded verdicts under the policy that produced them)
ERAS = {"23e (2.4.1, underscore era)": ("results/agbench-23e-2026-11-25", ("underscore",)),
        "26b (2.4.2, dash era)": ("results/agbench-26b", ("underscore", "dash"))}
present = {k: HERE / p for k, (p, _f) in ERAS.items() if (HERE / p / "sessions").exists()}
forms_of = {k: f for k, (_p, f) in ERAS.items()}
missing = [k for k in ERAS if k not in present]
for m in missing:
    print(f"  SKIP  {m}: wave dir not on disk (results dirs are gitignored)")

for era, wdir in present.items():
    print(f"  replaying {era}: {wdir.name}")
    drv.TOOL_FORMS.clear(); drv.TOOL_NAMES.clear()
    n_sessions = n_checked_leak = n_checked_probe = n_policy_diffs = 0
    era_ok = True
    for sd in sorted((wdir / "sessions").iterdir()):
        ef, rf = sd / "events.json", sd / "result.json"
        if not (ef.exists() and rf.exists()):
            continue
        n_sessions += 1
        ev = drv.parse_events(ef.read_text())
        rec = json.loads(rf.read_text())
        if not ev["tool_uses"]:
            # probe-dead attempts legitimately recorded before any tool event? keep honest
            check(f"{sd.name}: parsed >=1 tool event", False, "parser found nothing")
            era_ok = False
            continue
        # (a) seal audit must reproduce the recorded verdict under the era's policy
        if "seal_leaks" in rec:
            n_checked_leak += 1
            got = drv.seal_audit(ev["tool_uses"], forms=forms_of[era])
            want = rec["seal_leaks"]
            if got != want:
                era_ok = False
                check(f"{sd.name}: seal replay == recorded", False,
                      f"got {got} want {want}")
            # informational: what the CURRENT policy would say about the same stream
            now = drv.seal_audit(ev["tool_uses"])
            if now != want:
                n_policy_diffs += 1
        # (b) pure pool classifier must not contradict the recorded probe verdict
        #     (inline probe adds deadline kills the pure mirror lacks — skip those)
        pr = rec.get("probe") or {}
        why = str(pr.get("why") or "")
        if pr and "deadline" not in why and "no Resolve completion after" not in why:
            n_checked_probe += 1
            cp = drv.classify_pool(ef.read_text())
            if cp["dead"] != pr.get("dead") or (cp["ok"] != pr.get("ok") and not (cp["ok"] and pr.get("ok"))):
                era_ok = False
                check(f"{sd.name}: pool-classifier replay == recorded probe",
                      False, f"pure {cp} vs recorded {{'ok': {pr.get('ok')}, 'dead': {pr.get('dead')}}}")
        # (c) manifest observes without raising
        drv.manifest_observe(ev["tool_uses"])
    forms = drv.TOOL_FORMS
    any_completed = any(sum(v.values()) for v in forms.values())
    check(f"{era}: {n_sessions} sessions replayed ({n_checked_leak} seal, {n_checked_probe} probe verifications)",
          era_ok and any_completed,
          f"join forms: {json.dumps(forms)}")
    if n_policy_diffs:
        print(f"        note: {n_policy_diffs} sessions where the CURRENT naming policy "
              f"differs from the era's recorded verdicts (expected after policy bumps; "
              f"era replay above is the pin)")
    # era shape signal (reported, asserted softly: completed-call forms per era)
    def dominant(fs):
        t = {"underscore": 0, "dash": 0, "concat": 0}
        for v in fs.values():
            for k, n in v.items():
                t[k] += n
        return max(t, key=t.get) if any_completed else "none"
    print(f"        dominant completed-call join form: {dominant(forms)}")

# ---------- 4) fix-1/fix-2 instruments (2026-11-26) --------------------------
# schedule: forced-solo prefixes keep T7 out of every pair, order preserved
SEQ = ("T8r1,T8r2,T8r3,F2r1,F2r2,F2r3,T7r1,T7r2,T7r3,T1r1,T1r2,T1r3,"
       "T2r1,T2r2,T2r3,T3r1,T3r2,T3r3,F1r1,F1r2,F1r3").split(",")
lanes = drv.build_schedule(SEQ, ("T7",))
flat = [t for L in lanes for t in L[1:]]
check("build_schedule: order+coverage preserved, T7 never paired",
      flat == SEQ and all(not (L[0] == "pair" and (L[1].startswith("T7") or L[2].startswith("T7")))
                          for L in lanes))
check("build_schedule: empty prefixes == strict consecutive pairing (26b/26c behavior)",
      drv.build_schedule(SEQ, ()) == [("pair", SEQ[i], SEQ[i + 1]) for i in range(0, 20, 2)]
      + [("solo", SEQ[20])])
# 26d regression: solo task landing at an ODD position must break its pair too
# (the live 26d bug paired F1r3+T7r1 under the pre-fix scheduler; the wave RECORD
# documents the as-run buggy schedule - this pin guards the fix)
SEQ2 = ("F1r1,F1r2,F1r3,T7r1,T7r2,T7r3,T2r1,T2r2,T2r3,T8r1,T8r2,T8r3,F2r1,F2r2,"
        "F2r3,T3r1,T3r2,T3r3,T1r1,T1r2,T1r3").split(",")
lanes2 = drv.build_schedule(SEQ2, ("T7",))
check("build_schedule (26d order regression): T7r1 at odd position still runs solo",
      [t for L in lanes2 for t in L[1:]] == SEQ2
      and all(not (L[0] == "pair" and (L[1].startswith("T7") or L[2].startswith("T7")))
              for L in lanes2)
      and ("solo", "T7r1") in lanes2, str(lanes2[:3]))

# tri-state evidence grader (import the grading module too)
gspec = importlib.util.spec_from_file_location("gr", HERE / "grade_f1f2_wave.py")
gr = importlib.util.module_from_spec(gspec); gspec.loader.exec_module(gr)
tri = [({"comp_count": 1, "comp_names": ["Composition 1"]}, "pass"),
       ({"comp_count": 0, "agent_inwave_readbacks": [1, 1]}, "unmeasurable"),
       ({"comp_count": 0, "agent_inwave_readbacks": []}, "fail"),
       ({"comp_count": 0, "agent_inwave_readbacks": [0]}, "fail"),
       ({"error": "timeline not found"}, "unmeasurable")]
check("grade_t8_evidence: tri-state (pass / churn-unmeasurable / trap-fail)",
      all(gr.grade_t8_evidence(ev)[0] == want for ev, want in tri))

# in-wave scanner against RECORDED sessions: T8 read-backs must be found in both eras
for era in present:
    rb = drv.agent_inwave_readbacks(present[era] / "sessions" / "T8r1" / "events.json")
    check(f"{era}: T8r1 in-wave comp read-backs found via events.json",
          bool(rb) and any(v >= 1 for v in rb), str(rb[:6]))

print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILURES: {fails}")
sys.exit(1 if fails else 0)
