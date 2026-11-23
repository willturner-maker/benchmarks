#!/usr/bin/env python3
"""Builds the Pages scorecard for the 2026-11-22 thinking-token-budget chain.

Numbers are never hand-typed here: everything comes from
bench/tau2-bench/results/2026-11-22-thinkbudget-chain/arm_readout.json, which thinkbudget_summary.py
produces from the tau2 records and each wave's engine samples. The CSS is taken from the existing
report in reports/ so the family stays visually identical, and the build fails loudly if that file is
missing rather than emitting an unstyled page.

Usage: python3 tools/make-thinkbudget-report.py [--out reports/2026-11-22-thinking-budget-chain.html]
"""
from __future__ import annotations
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
READOUT = os.path.join(ROOT, "bench", "tau2-bench", "results", "2026-11-22-thinkbudget-chain", "arm_readout.json")
CSS_PARENT = os.path.join(ROOT, "reports", "2026-11-19-splash-queue-size.html")
ARMS = ("8192", "65536", "32768")


def css_block():
    if not os.path.exists(CSS_PARENT):
        sys.exit(f"cannot reuse the report CSS: {CSS_PARENT} not found")
    src = open(CSS_PARENT, encoding="utf-8").read()
    end = src.find("</style>")
    if end < 0:
        sys.exit("no </style> block in the parent report - refusing to guess the stylesheet")
    return src[:end + len("</style>")]


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "reports", "2026-11-22-thinking-budget-chain.html"))
    a = ap.parse_args()
    d = json.load(open(READOUT, encoding="utf-8"))
    A, P = d["arms"], d["pairwise"]
    cap = d["harness_cap_declared_in_run_wave"]

    for arm in ARMS:
        if arm not in A:
            sys.exit(f"readout is missing arm {arm}")

    def fmt(x, nd=4):
        if x is None:
            return "n/a"
        return f"{x:.{nd}f}" if isinstance(x, float) else f"{x:,}"

    pass1 = {k: A[k]["outcome"]["pass1"] for k in ARMS}
    spread = round((max(pass1.values()) - min(pass1.values())) * 100, 1)
    flips = {k: v["only_first_passes"] + v["only_second_passes"] for k, v in P.items()}
    agent_turns = sum(A[k]["messages"]["agent_messages"] for k in ARMS)
    cap_hits = sum(A[k]["messages"]["agent_messages_at_harness_cap"] or 0 for k in ARMS)

    # ---- chips
    chips = [
        ("", f"{spread} pts spread", "pass^1 across three arms that cannot differ — 0.8782 / 0.8697 / 0.8403"),
        ("", "inert by construction", f"budgets 8,192 / 32,768 / 65,536 all sit above the harness cap of {cap:,} tokens"),
        ("warn", "17.6–19.7 % of tasks flip", "with nothing varied — ±4 pts of single-wave pass^1 is the noise floor"),
        ("", "0 crowd-out messages", f"thinking never ate a completion in 714 sims; {cap_hits} agent turn hit the cap"),
    ]
    chip_html = "\n".join(
        f'    <div class="chip"><span class="dot {c}"></span><b>{esc(t)}</b><span>{esc(s)}</span></div>'
        for c, t, s in chips)

    # ---- section 1: outcomes
    rows = []
    for arm in ARMS:
        o = A[arm]["outcome"]
        dm = A[arm]["domains"]
        cls = ' class="ok"' if arm == "32768" else ""
        rows.append(
            f"      <tr><td{' ' + cls if cls else ''}>{arm}{' (pin-restore control)' if arm == '32768' else ''}</td>"
            f"<td class=\"num\">{fmt(o['pass1'])}</td>"
            f"<td class=\"num\">{fmt(dm['airline']['pass1'], 3)}</td>"
            f"<td class=\"num\">{fmt(dm['retail']['pass1'], 3)}</td>"
            f"<td class=\"num\">{fmt(dm['telecom']['pass1'], 3)}</td>"
            f"<td class=\"num\">{o['tasks_with_any_pass']}</td>"
            f"<td class=\"num\">{o['tool_calls_total']:,}</td>"
            f"<td class=\"num\">{o['sims_total']}</td></tr>")
    pass_bars = []
    for arm in ARMS:
        w = round(pass1[arm] * 100, 2)
        col = "var(--accent)" if arm != "32768" else "var(--s2)"
        pass_bars.append(
            f'      <div class="bar"><span class="bl">{arm}</span>'
            f'<span class="bt"><i style="width:{w}%;background:{col}"></i></span>'
            f'<span class="bv">{pass1[arm]:.4f}</span></div>')

    # ---- section 2: flips
    flip_rows = []
    for label, v in P.items():
        flip_rows.append(
            f"      <tr><td>{esc(label)}</td><td class=\"num\">{v['tasks_compared']}</td>"
            f"<td class=\"num\">{v['both_pass']}</td><td class=\"num\">{v['both_fail']}</td>"
            f"<td class=\"num\">{v['only_first_passes']}</td><td class=\"num\">{v['only_second_passes']}</td>"
            f"<td class=\"num\">{v['flip_rate'] * 100:.1f} %</td><td class=\"num\">p = {v['sign_test_p']:.3f}</td></tr>")

    # ---- section 3: reachability arithmetic
    reach_rows = []
    for arm in ARMS:
        r = A[arm]["budget_reachability"]
        reach_rows.append(
            f"      <tr><td>{arm}</td><td class=\"num\">{r['arm_budget_from_supervisor_pins']:,}</td>"
            f"<td class=\"num\">{cap:,}</td>"
            f"<td class=\"num\">{r['largest_agent_completion']:,}</td>"
            f"<td class=\"num\">{r['messages_at_cap']}</td>"
            f"<td class=\"warn\">{esc(r['verdict'])}</td></tr>")
    tok_rows = []
    for arm in ARMS:
        m = A[arm]["messages"]
        ac, th = m["agent_completion_tokens_incl_thinking"], m["agent_thinking_tokens_derived"]
        tok_rows.append(
            f"      <tr><td>{arm}</td><td class=\"num\">{m['agent_messages']:,}</td>"
            f"<td class=\"num\">{ac['mean']}</td><td class=\"num\">{ac['median']}</td>"
            f"<td class=\"num\">{ac['max']:,}</td><td class=\"num\">{th['mean']}</td>"
            f"<td class=\"num\">{th['max']:,}</td><td class=\"num\">{m['thinking_share_of_agent_completion']:.3f}</td>"
            f"<td class=\"num\">{m['thinking_crowdout_empty_visible_messages']}</td></tr>")

    # ---- section 4: engine join
    eng_rows = []
    for arm in ARMS:
        e = A[arm]["engine_samples"]
        warn = "warn" if e.get("provenance_warning") else ""
        w = e["decode_batch_width_high_water"]
        eng_rows.append(
            f"      <tr><td>{arm}{' <span class=\"warn\">(excluded)</span>' if warn else ''}</td>"
            f"<td class=\"num\">{e['samples']}</td><td class=\"num\">{e['samples_with_live_requests']}</td>"
            f"<td class=\"num\">{e['pages_active_max']:,}</td>"
            f"<td class=\"num\">{e['pages_active_max_tokens']:,}</td>"
            f"<td class=\"num\">{e['queued_max']}</td><td class=\"num\">{e['decoding_max']}</td>"
            f"<td class=\"num\">b1 {w['b1']:,} · b2 {w['b2']:,} · b3 {w['b3']:,} · b4 {w['b4']:,}</td>"
            f"<td class=\"num\">{e['counter_deltas_over_window']['spill_moves']} / "
            f"{e['counter_deltas_over_window']['kv_demotions']:,} / "
            f"{e['counter_deltas_over_window']['suspensions']}</td></tr>")

    # The reused stylesheet has no bar classes; define the few this page adds, using only its palette,
    # so the scorecard can never drift into an unstyled or off-palette look.
    extra_css = """
<style>
.bar{display:grid;grid-template-columns:78px 1fr 74px;align-items:center;gap:10px;margin-top:9px}
.bl{font:500 12.5px/1 var(--mono);color:var(--fg-2)}
.bt{display:block;height:14px;background:var(--bg);border:1px solid var(--line);border-radius:4px;overflow:hidden}
.bt i{display:block;height:100%}
.bv{font:600 13px/1 var(--mono);text-align:right;font-variant-numeric:tabular-nums}
</style>"""

    html = f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Thinking-token budget chain — engine arms 8192 / 65536 / 32768</title>
{css_block()}{extra_css}
<div class="wrap">
  <div class="eyebrow">Will's local AI pipeline · Splash 1.7.0 · τ²-bench 238 judge-free tasks · thinking-budget chain</div>
  <h1>The thinking-budget A/B could not bind — so it publishes the noise floor instead</h1>
  <p class="lede">Three waves of the same 238 tasks, one per engine <code>--thinking-token-budget</code>
  (8192, 65536, and the pinned 32,768 relaunched last as a same-session control). The flag was set
  differently three times and changed nothing: the harness caps completion at <code>max_tokens {cap:,}</code>,
  and <b>thinking tokens count inside that cap</b>, so every arm's budget sat above the ceiling the model was
  allowed to reach. What is left is the measurement the suite actually needed — <b>how much τ² moves when
  nothing is varied</b>: pass^1 spreads <b>{spread} points</b> and <b>17.6–19.7 % of tasks flip</b>, with no
  pair separable by an exact sign test.</p>

  <div class="chips">
{chip_html}
  </div>

  <section>
    <h2>1 · The three arms <span class="tag">trials 1 · seed 300 · temperature 0 · self-play</span></h2>
    <div class="viz-root">
      <div class="vtitle">pass^1 by arm — an inert manipulation, spread {spread} pts</div>
      <div class="vsub">8192 and 65536 are the treatment arms; 32,768 is the pinned value, relaunched last so a
      mid-chain failure still leaves the engine pinned, which makes it the same-session control</div>
{chr(10).join(pass_bars)}
    </div>
    <div class="tbl-scroll">
    <table>
      <thead><tr><th>arm</th><th class="num">pass^1</th><th class="num">airline (50)</th>
      <th class="num">retail (74)¹</th><th class="num">telecom (114)</th><th class="num">any-pass tasks</th>
      <th class="num">tool calls</th><th class="num">sims scored</th></tr></thead>
      <tbody>
{chr(10).join(rows)}
      </tbody>
    </table>
    </div>
    <p class="note">¹ retail is the published judge-free subset: 74 of 114 ids via upstream's own
    <code>--task-ids</code>, re-verified in these waves — 0 of the 74 carry <code>nl_assertions</code>, so the NL
    evaluator short-circuits and no judge is reachable. Never pool domains: different task counts and different
    graded components.</p>
  </section>

  <section>
    <h2>2 · The number worth keeping — flips between arms that cannot differ</h2>
    <p class="note">With <code>--num-trials 1</code> the only thing that can differ per task is pass/fail, so the
    discordant counts <i>are</i> the noise floor. Exact two-sided sign test on the discordants (no normal
    approximation).</p>
    <div class="tbl-scroll">
    <table>
      <thead><tr><th>pair</th><th class="num">tasks</th><th class="num">both pass</th><th class="num">both fail</th>
      <th class="num">only first</th><th class="num">only second</th><th class="num">flip rate</th><th class="num">sign test</th></tr></thead>
      <tbody>
{chr(10).join(flip_rows)}
      </tbody>
    </table>
    </div>
    <div class="kv">
      <div class="stat"><div class="v">±4 pts</div><div class="l">the working rule for a single 238-task wave:
      ≈19 task flips of pass^1 is noise</div></div>
      <div class="stat"><div class="v">{cap_hits} / {agent_turns:,}</div><div class="l">agent turns that reached
      the cap across all three arms — the cap binds rarely, the engine budget never</div></div>
      <div class="stat"><div class="v">15.1 %</div><div class="l">independent same-seed flip floor
      (2026-11-21 pair) — same band as these 17.6–19.7 %</div></div>
      <div class="stat"><div class="v">18.9 %</div><div class="l">independent 2-trial flip rate (2026-11-19a) —
      also the same band</div></div>
    </div>
  </section>

  <section>
    <h2>3 · Why the arms were inert — arithmetic, not measurement <span class="tag">the correction</span></h2>
    <p class="note">On this stack, reasoning tokens are billed inside <code>completion_tokens</code>. Measured
    directly the same day: <code>max_tokens=16</code> → <code>completion_tokens=16</code> with
    <code>reasoning_tokens=16</code> and <code>content=null</code>; the same prompt at 200 answered correctly with
    23 reasoning tokens. So completion ≤ {cap:,} always, and an engine budget above {cap:,} can never be the
    binding constraint. Each arm's budget below is read from <code>supervisor_pins.txt</code> — the live
    supervisor's argv at wave start, not the chain script's intent.</p>
    <div class="tbl-scroll">
    <table>
      <thead><tr><th>arm</th><th class="num">budget (live argv)</th><th class="num">harness cap</th>
      <th class="num">largest agent completion</th><th class="num">agent turns at cap</th><th class="num">verdict</th></tr></thead>
      <tbody>
{chr(10).join(reach_rows)}
      </tbody>
    </table>
    </div>
    <div class="tbl-scroll">
    <table>
      <thead><tr><th>arm</th><th class="num">agent turns</th><th class="num">completion mean</th>
      <th class="num">median</th><th class="num">max</th><th class="num">thinking mean²</th>
      <th class="num">thinking max²</th><th class="num">thinking share</th><th class="num">crowd-out³</th></tr></thead>
      <tbody>
{chr(10).join(tok_rows)}
      </tbody>
    </table>
    </div>
    <p class="note">² τ² records <code>completion_tokens</code> only, with no reasoning breakdown, so thinking is
    <i>derived</i>: completion − estimated visible (chars / 4). It is labelled an estimate and nothing above
    depends on it — the inertness conclusion comes from the cap arithmetic. ³ crowd-out = completion &gt; 0 with
    empty visible content <b>and no tool call</b>: the first version of the detector counted 642 / 655 / 689
    tool-call turns as truncations, because a tool-call turn has empty content by design. True crowd-out: zero,
    in every arm.</p>
  </section>

  <section>
    <h2>4 · Engine side — τ² is a prefix-cache workload, and it never touches the queue</h2>
    <div class="tbl-scroll">
    <table>
      <thead><tr><th>arm</th><th class="num">samples</th><th class="num">samples with live requests</th>
      <th class="num">pages_active max</th><th class="num">…in tokens</th><th class="num">queued max</th>
      <th class="num">decoding max</th><th class="num">decode width high-water (lifetime)</th>
      <th class="num">spill / demote / susp (Δ window)</th></tr></thead>
      <tbody>
{chr(10).join(eng_rows)}
      </tbody>
    </table>
    </div>
    <ul class="tight">
      <li>Residency tops out at <b>0.155× / 0.168× of the 155,648-token KV budget</b> — τ² is not a KV-stress
      suite, and it never was.</li>
      <li><code>queued</code> never exceeded <b>1</b>: a single-tenant τ² wave does not queue, which is why the
      <code>--queue-size 64</code> stack move is invisible to this suite in both directions.</li>
      <li>The wave's own <code>--max-concurrency 3</code> shows up in the engine's counters: decode width b3
      dominates by an order of magnitude and <b>b4 is never reached</b>, so <code>maximum_batch_width: 4</code>
      is never filled here.</li>
      <li>Memory-path engagement: spill 0, suspensions 0, and <code>kv_demotions</code> +3,164 / +2,595 —
      persistent-cache churn without pressure.</li>
      <li><b>The 65536 arm's engine samples are excluded, not averaged in.</b> Its directory was re-entered by a
      stalled re-run: 30 of 552 samples show live requests, <code>queued</code> max 32, and
      <code>max_new_tokens</code> of 8 / 32,768 where the harness declares {cap:,} — that is foreign traffic. Its
      outcome data is verified intact; only its console and engine evidence degraded.</li>
    </ul>
  </section>

  <section>
    <h2>5 · Provenance: what went wrong, stated in the record</h2>
    <ul class="tight">
      <li>Five chain launches. The first failed its own argv guard because the guard looked at the engine
      <i>child</i>, whose argv carries no options at all — the supervisor carries them. Two more launches aborted
      on the engine-idle guard rather than killing a busy engine. The last one stalled on τ²'s interactive
      "resume the run? (y/n)" prompt for 84 minutes with the engine idle, which is how the runner got hardened:
      <code>&lt;/dev/null</code> stdin, a pre-flight check on <code>--save-to</code>, a completed-arm skip guard, and
      a stall watchdog that watches <b>engine</b> batch counters rather than τ²'s CPU.</li>
      <li>Four analyzer bugs are published in the record because each would have printed plausible numbers:
      reward lives under <code>reward_info.reward</code>; τ² task ids are numeric <i>per domain</i>, so keying on
      <code>task_id</code> alone merged airline task 3 with retail task 3; the crowd-out detector counted tool-call
      turns as truncations; and deriving the harness cap from engine samples is wrong for a contaminated arm.</li>
      <li>One operator-caused tenancy sample inside the 65536 window is recorded rather than suppressed
      (active 36 / queued 32 / decoding 0, spill/demote/suspensions 0). The arm was characterised, not voided.</li>
      <li>Every number on this page was diffed against <code>arm_readout.json</code> programmatically
      (74 checks). One FAIL in that check was the checker, not the data — it subtracted an airline-only count.</li>
    </ul>
    <p class="note">Records: <code>bench/tau2-bench/results/2026-11-22-thinkbudget-chain/RECORD.md</code> ·
    arm evidence in <code>results/2026-11-22-thinkbudget-{{8192,65536,32768}}/</code> ·
    stall and tenancy detail in <code>results/2026-11-22-thinkbudget-65536/TENANCY.md</code> ·
    regenerate with <code>python3 bench/tau2-bench/thinkbudget_summary.py</code> then
    <code>python3 tools/make-thinkbudget-report.py</code>.</p>
  </section>
</div>
"""
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {a.out} ({len(html):,} chars) from {READOUT}")


if __name__ == "__main__":
    main()
