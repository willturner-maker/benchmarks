#!/usr/bin/env python3
"""Golden probes: the fixed request set to re-run on both sides of a Splash version transition.

What it is NOT: a benchmark. No scores come out of this. It answers one question - did the engine's
*behaviour* move - with byte comparisons, so that a version delta in a scored row can be called an
effect rather than an unexplained shift.

Design notes that matter:

  * Every probe runs TWICE in the same capture, and the two are byte-compared. That is the
    self-reproducibility floor of the current build, and it is what licenses the cross-version claim:
    if a probe does not reproduce within 1.7.0, a 1.7.0-vs-1.7.1 difference on that probe proves
    nothing about the version. (This suite already knows the floor is low for agent transcripts -
    0/238 byte-identical at identical seeds - so short deterministic prompts are used on purpose.)
  * `verify_rows` is read from the live engine and recorded, not assumed. `--verify-rows all` is
    upstream's repeatability switch; the current pinned stack runs `auto`. Whichever it is, it goes in
    the record, because the two modes have different byte physics.
  * The probe set is chosen from what the release notes touch, and from our own records: greedy
    decode, streaming + tool-call grammars with nested arrays (1.7.1 fixes a streamed json_schema
    verify-mask failure that hit ~1 % of such requests with reasoning off), the thinking-budget
    crowd-out signature we measured on this stack, the shared system+tools head (1.7.1 caches a state
    at the head's end: 2.5-2.9x faster TTFT upstream), a cold-then-warm 2K prefill, and the 63-vs-72
    token uncached follow-up (1.7.1's own known issue on GGUF weights).

Usage: python3 golden_probes.py [--out FILE] [--port 8000] [--probes decode,...]
"""
from __future__ import annotations
import argparse
import hashlib
import json
import time
import urllib.request

BASE = "http://127.0.0.1:{port}"
FILLER_A = ("The maintenance log for pump station {i} records the following observations, each one "
            "checked twice against the pressure gauge and the flow meter. ")
# A second filler, deliberately different text, so the long-prompt probes do not share cached
# prefixes with each other: a follow-up probe whose "head" was already served by an earlier probe
# would silently become a cache-hit probe, and the 1.7.1 uncached-follow-up issue needs uncached.
FILLER_B = ("Inventory sheet {i} of the depot lists crates, each crate weighed on the platform scale "
            "and reconciled against the shipping manifest and the dock register. ")


def sha(s):
    return hashlib.sha256((s or "").encode("utf-8", "replace")).hexdigest()[:32]


def visible(r):
    """The part of a response a harness actually consumes: content, tool-call arguments, stop reason.

    Kept separate from reasoning on purpose. The first capture of this instrument showed probes whose
    visible output was byte-identical across repeats while the reasoning stream differed, so a single
    combined hash would report "changed" on probes where nothing the caller sees moved - and 1.7.1
    explicitly shifts reasoning length, which would bury the signal.
    """
    return (r.get("content_sha"),
            tuple(sorted((str(t.get("name")), t.get("args_sha")) for t in r.get("tool_calls") or [])),
            r.get("finish"))


def payload(r):
    """Canonical form of a grammar-constrained body: parsed JSON with sorted keys, or INVALID.

    Grammar probes get their own comparison because a JSON body has degrees of freedom a byte hash
    punishes for no reason. The capture that introduced this showed two runs of the same streamed
    json_schema request both valid, both accepted by the grammar, differing only by an empty
    `"flags": []` the model chose to emit or omit: a byte diff there is not a version effect.
    """
    body = r.get("content")
    try:
        return hashlib.sha256(json.dumps(json.loads(body), sort_keys=True).encode()).hexdigest()[:32]
    except Exception:
        return None


def visible_g(outer):
    """Grammar variant: compare parsed payload and stop reason, not raw bytes."""
    return (payload(outer), outer.get("finish"))


def cmp_for(kind):
    return {"byte": visible, "grammar": visible_g}.get(kind)


def compare(prev_path, cur_path):
    """Cross-capture delta: what moved between two captures of the same probe set."""
    prev, cur = json.load(open(prev_path)), json.load(open(cur_path))
    pp, cp = prev.get("probes") or {}, cur.get("probes") or {}
    print(f"== {prev_path} ({prev.get('captured_at_utc')}, nonce {prev.get('nonce')})")
    print(f"-> {cur_path} ({cur.get('captured_at_utc')}, nonce {cur.get('nonce')})")
    for k in sorted(set(pp) | set(cp)):
        if k not in pp or k not in cp:
            print(f"  {k:<26} only in {'current' if k not in pp else 'previous'} capture")
            continue
        a, b = pp[k]["runs"][0], cp[k]["runs"][0]
        if "error" in a or "error" in b:
            print(f"  {k:<26} error in one capture: {a.get('error') or b.get('error')}")
            continue
        ua, ub = a.get("usage") or {}, b.get("usage") or {}
        cmpf = cmp_for(cp[k].get("kind"))
        byte = cmpf is not None and not cp[k].get("order_sensitive")
        tags = []
        moved = bool(byte and cmpf is not None and cmpf(a) != cmpf(b))
        if moved:
            tags.append(f"OUTPUT MOVED (compared as {cp[k].get('kind')})")
        elif cmpf is None and visible(a) != visible(b):
            tags.append("output differs (timing probe: no byte claim)")
        if a["reasoning_sha"] != b["reasoning_sha"]:
            tags.append("reasoning moved")
        if ua.get("completion_tokens") != ub.get("completion_tokens"):
            tags.append(f"completion {ua.get('completion_tokens')}->{ub.get('completion_tokens')}")
        head = "SAME" if not tags else ("DIFF" if byte else "usage")
        print(f"  {k:<26} {head:<5} prompt {ua.get('prompt_tokens')}->{ub.get('prompt_tokens')} "
              f"cached {(ua.get('prompt_tokens_details') or {}).get('cached_tokens')}"
              f"->{(ub.get('prompt_tokens_details') or {}).get('cached_tokens')} "
              f"{' '.join(tags)}")
        if moved:
            print(f"      prev content={a['content_sha']} tools={visible(a)[1]}")
            print(f"      cur  content={b['content_sha']} tools={visible(b)[1]}")


def model_id(base):
    return json.load(urllib.request.urlopen(base + "/v1/models", timeout=20))["data"][0]["id"]


def call(base, model, body, stream=False):
    """One request. Returns record with usage, byte hashes, and measured timings."""
    payload = dict(body)
    payload["model"] = model
    if stream:
        payload["stream"] = True
        # without this the engine sends no usage on a stream, and the probe cannot report what it
        # prompted or what it cached - which is the whole point of the streaming probes.
        payload["stream_options"] = {"include_usage": True}
    req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        if not stream:
            d = json.loads(r.read().decode())
            ttft = None
        else:
            first = None
            choice = {"content": "", "reasoning_content": "", "tool_calls": []}
            usage, finish = None, None
            for raw in r:
                line = raw.decode().strip()
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                c = json.loads(chunk)
                if c.get("usage"):
                    usage = c["usage"]
                ch = (c.get("choices") or [{}])[0]
                if ch.get("finish_reason"):
                    finish = ch["finish_reason"]
                delta = ch.get("delta") or {}
                if first is None and (delta.get("content") or delta.get("reasoning_content")
                                      or delta.get("tool_calls")):
                    first = time.time()
                choice["content"] += delta.get("content") or ""
                choice["reasoning_content"] += delta.get("reasoning_content") or ""
                for t in delta.get("tool_calls") or []:
                    fn = (t.get("function") or {})
                    idx = t.get("index", 0)
                    while len(choice["tool_calls"]) <= idx:
                        choice["tool_calls"].append({"name": "", "arguments": ""})
                    choice["tool_calls"][idx]["name"] += fn.get("name") or ""
                    choice["tool_calls"][idx]["arguments"] += fn.get("arguments") or ""
            ttft = round((first - t0) * 1000, 1) if first else None
            d = {"choices": [{"message": choice, "finish_reason": finish}], "usage": usage}
    total = round((time.time() - t0) * 1000, 1)
    msg = d["choices"][0]["message"]
    tools = msg.get("tool_calls") or []
    return {
        "content_sha": sha(msg.get("content")), "content_len": len(msg.get("content") or ""),
        "reasoning_sha": sha(msg.get("reasoning_content")), "content": msg.get("content"),
        "reasoning_head": (msg.get("reasoning_content") or "")[:120],
        "tool_calls": [{"name": t.get("name") or (t.get("function") or {}).get("name"),
                        "args_sha": sha(t.get("arguments") or (t.get("function") or {}).get("arguments"))}
                       for t in tools],
        "finish": d["choices"][0].get("finish_reason"), "usage": d.get("usage"),
        "ttft_ms": ttft, "total_ms": total,
    }


NESTED_TOOLS = [{
    "type": "function",
    "function": {
        "name": "record_readings",
        "description": "Return structured readings for the stations named in the message.",
        "parameters": {
            "type": "object",
            "properties": {
                "stations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "pressures": {"type": "array", "items": {"type": "number"}},
                            "flags": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["id", "pressures"],
                    },
                }
            },
            "required": ["stations"],
        },
    },
}]

# The shared head for the cross-session probes: long enough to be worth caching (~250 tokens) and
# byte-identical between the two sessions, which is the condition 1.7.1's shared-head state cache
# needs. Two different one-line system messages would not exercise it.
SHARED_HEAD = (
    "You are the duty engineer's assistant for a water district that runs pump stations. "
    + " ".join(
        f"Rule {i}: when a station's reading disagrees with its paired instrument, trust the gauge "
        f"that was calibrated most recently, log the disagreement against station {i:02d}, and never "
        "change a setpoint without a second confirmation."
        for i in range(1, 11)
    )
)


JSON_SCHEMA_NESTED = {
    "type": "json_schema",
    "json_schema": {
        "name": "readings",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "stations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "pressures": {"type": "array", "items": {"type": "number"}},
                            "flags": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["id", "pressures"],
                    },
                }
            },
            "required": ["stations"],
        },
    },
}


def probe_set(port, nonce="1"):
    """The fixed set. Each entry: (name, kind, body, stream, order_sensitive).

    `kind` decides what a capture may later claim about that probe:
      "byte"     short greedy or tool-call output. Byte-comparable within a build, so a byte
                 difference across builds is a finding.
      "grammar"  json_schema-constrained body. Compared as a parsed payload (see `payload`), because
                 the grammar leaves degrees of freedom a byte hash would punish.
      "timing"   prose or latency-shaped (shared heads, big prefills). Measured for TTFT, cached
                 tokens and completion length; NOT byte-comparable, proved by the first capture where
                 prose at temperature 0 differed run to run. A cross-version diff reads usage, not bytes.
    `order_sensitive` probes run ONCE: their value is being cold or being second, so a repeat would
    measure a different thing and byte-checking them by repetition is not available.

    `nonce` appears only inside the long-prompt probes. With `--persistent-cache` on, a 2K prompt stays
    cached across engine restarts, so a "cold" prefill probe would be warm in every capture after the
    first - which is exactly what happened when the first version of this instrument re-ran it. A
    per-capture nonce keeps every cold probe genuinely cold; the two captures then compare equal-size
    prompts that are not the same prompt, and the measured token counts of both are printed so that
    claim is checkable rather than asserted.
    """
    big_a = (f"Capture reference {nonce}. " + " ".join(FILLER_A.format(i=i) for i in range(1, 68)))
    big_b = (f"Capture reference {nonce}. " + " ".join(FILLER_B.format(i=i) for i in range(1, 68)))
    # A real shared head: the same long system message + the same tool schema in every session of a
    # suite is what 1.7.1 says it can cache a state for. A one-line system message would not test it.
    head = {"role": "system", "content": SHARED_HEAD}
    return [
        ("decode_greedy_64", "byte", {"temperature": 0, "max_tokens": 64,
                                      "messages": [{"role": "user",
                                                    "content": "List the twelve months of the year, one per line, in order."}]}, False, False),
        ("thinking_crowdout_16", "byte", {"temperature": 0, "max_tokens": 16,
                                          "messages": [{"role": "user", "content": "Say READY."}]}, False, False),
        ("thinking_room_256", "byte", {"temperature": 0, "max_tokens": 256,
                                       "messages": [{"role": "user", "content": "Say READY."}]}, False, False),
        ("toolcall_nested_forced", "byte", {"temperature": 0, "max_tokens": 256, "tools": NESTED_TOOLS,
                                            "tool_choice": {"type": "function", "function": {"name": "record_readings"}},
                                            "messages": [{"role": "user",
                                                          "content": "Stations A7 and B2. A7 read 41 then 43; B2 read 38, 39, 44. "
                                                                     "B2 had flags 'surge' and 'reset'. Call the tool."}]}, False, False),
        ("toolcall_nested_stream", "byte", {"temperature": 0, "max_tokens": 256, "tools": NESTED_TOOLS,
                                            "tool_choice": {"type": "function", "function": {"name": "record_readings"}},
                                            "messages": [{"role": "user",
                                                          "content": "Stations C1 and D9. C1 read 52 then 51; D9 read 60, 61, 62. "
                                                                     "D9 had flags 'overshoot'. Call the tool."}]}, True, False),
        ("json_schema_crowdout_64", "byte", {"temperature": 0, "max_tokens": 64,
                                             "response_format": JSON_SCHEMA_NESTED,
                                             "messages": [{"role": "user",
                                                           "content": "Stations E3 (readings 21, 22, 25) and F8 (readings 30, 31). "
                                                                      "F8 had flags 'cavitation'. Return them."}]}, False, False),
        ("json_schema_nested", "grammar", {"temperature": 0, "max_tokens": 512,
                                           "response_format": JSON_SCHEMA_NESTED,
                                           "messages": [{"role": "user",
                                                         "content": "Stations E3 (readings 21, 22, 25, flags 'cavitation') and "
                                                                    "F8 (readings 30, 31, flags 'idle'). Return both."}]}, False, False),
        ("json_schema_nested_stream", "grammar", {"temperature": 0, "max_tokens": 512,
                                                  "response_format": JSON_SCHEMA_NESTED,
                                                  "messages": [{"role": "user",
                                                                "content": "Stations G5 (readings 47, 48, flags 'low') and "
                                                                           "H1 (readings 55, 56, 58, flags 'surge'). Return both."}]}, True, False),
        ("shared_head_session_a", "timing", {"temperature": 0, "max_tokens": 160, "tools": NESTED_TOOLS,
                                             "messages": [head,
                                                          {"role": "user", "content": "In one sentence: what should I check first if station A7 reads high?"}]}, False, False),
        ("shared_head_session_b", "timing", {"temperature": 0, "max_tokens": 160, "tools": NESTED_TOOLS,
                                             "messages": [head,
                                                          {"role": "user", "content": "In one sentence: what should I check first if station Q4 reads low?"}]}, False, False),
        ("prefill_cold_2k", "timing", {"temperature": 0, "max_tokens": 32,
                                       "messages": [{"role": "user", "content": big_a + "\nSummarise the log in one sentence."}]}, False, True),
        # Same body, run straight after the cold one: the TTFT gap between these two IS the prefix
        # cache working, and 1.7.1 claims to move the cold side of it.
        ("prefill_warm_2k", "timing", {"temperature": 0, "max_tokens": 32,
                                       "messages": [{"role": "user", "content": big_a + "\nSummarise the log in one sentence."}]}, False, True),
        ("followup_63", "timing", {"temperature": 0, "max_tokens": 24, "target_msg_tokens": 63,
                                   "messages": [{"role": "user", "content": big_b},
                                                {"role": "assistant", "content": "Logged."},
                                                {"role": "user", "content": "Roughly how many crates appear? Digits only."}]}, False, False),
        ("followup_72", "timing", {"temperature": 0, "max_tokens": 24, "target_msg_tokens": 72,
                                   "messages": [{"role": "user", "content": big_b},
                                                {"role": "assistant", "content": "Logged."},
                                                {"role": "user", "content": "Roughly how many crates appear in the list above? Digits only, nothing else."}]}, False, False),
    ]


def calibrate(base, model, msg, target, tol=3, tries=6):
    """Pad a message with whole words until IT costs about `target` prompt tokens.

    Why not calibrate on total prompt tokens: the follow-up probes exist to compare a 63-token
    follow-up against a 72-token one on top of a ~2K-token head (1.7.1's own known issue #2, GGUF
    uncached follow-ups). The first version of this instrument targeted total prompt tokens, which can
    never be 63 with a 2K head, so it padded with empty strings and quietly shipped a pair that
    differed by 7 tokens of trailing spaces. Measuring the message on its own is the only way to hit
    the number the probe is named after.
    """
    words = "please recheck the gauge log now and then "
    cur = msg
    got = None
    for _ in range(tries):
        probe = {"temperature": 0, "max_tokens": 1, "messages": [{"role": "user", "content": cur}]}
        try:
            r = call(base, model, probe)
        except Exception:
            return cur, None
        got = (r.get("usage") or {}).get("prompt_tokens")
        if got is None:
            return cur, None
        # 1 = the single completion token requested; the boilerplate of this one-message probe is what
        # the caller compares against, so the value returned is the message's measured cost as billed.
        if abs(got - target) <= tol:
            return cur, got
        if got < target:
            cur = cur + " " + words * max(1, (target - got) // 7)
        else:
            keep = max(1, len(cur) - (got - target) * 5)
            cur = cur[:keep].rstrip()
    return cur, got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="8000")
    ap.add_argument("--out", default=None)
    ap.add_argument("--probes", default=None, help="comma-separated names to run (default: all)")
    ap.add_argument("--compare", nargs=2, metavar=("PREV", "CUR"),
                    help="skip probing; print the delta between two captures")
    ap.add_argument("--nonce", default=None,
                    help="per-capture token put inside the long-prompt probes so a cold prefill stays cold")
    a = ap.parse_args()
    if a.compare:
        compare(*a.compare)
        return
    nonce = a.nonce or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    base = BASE.format(port=a.port)
    model = model_id(base)
    st = json.load(urllib.request.urlopen(base + "/status", timeout=20))
    want = set(a.probes.split(",")) if a.probes else None

    out = {
        "captured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nonce": nonce,
        "model": model, "verify_rows": st.get("verify_rows"),
        "maximum_context_tokens": st.get("maximum_context_tokens"),
        "ane_ffn_state": (st.get("ane_ffn") or {}).get("state"),
        "identity_cache": (st.get("identity") or {}).get("cache"),
        "scheduler_before": st.get("scheduler"), "probes": {},
    }
    for name, kind, body, stream, order_sensitive in probe_set(a.port, nonce):
        if want and name not in want:
            continue
        target = body.pop("target_msg_tokens", None)
        calibrated_to = None
        if target:
            body["messages"][-1]["content"], calibrated_to = calibrate(
                base, model, body["messages"][-1]["content"], target)
        attempts = 1 if order_sensitive else 2
        runs = []
        for _attempt in range(attempts):
            try:
                r = call(base, model, body, stream)
                r["payload_sha"] = payload(r)
                runs.append(r)
            except Exception as e:
                runs.append({"error": f"{type(e).__name__}: {e}"})
        ok2 = len(runs) == 2 and all("error" not in r for r in runs)
        if kind == "byte":
            cmpf = visible
        elif kind == "grammar":
            cmpf = visible_g
        else:
            cmpf = None
        if cmpf is None or order_sensitive:
            vis = rea = None  # no byte/payload claim for timing probes or single-run probes
        else:
            vis = ok2 and cmpf(runs[0]) == cmpf(runs[1])
            rea = ok2 and runs[0]["reasoning_sha"] == runs[1]["reasoning_sha"]
        out["probes"][name] = {
            "kind": kind, "byte_claim": cmpf is not None and not order_sensitive,
            "compare_as": kind, "visible_output_reproducible": vis, "reasoning_reproducible": rea,
            "order_sensitive": order_sensitive,
            "target_msg_tokens": target, "calibrated_msg_tokens": calibrated_to,
            "request": body, "runs": runs,
        }
        u = (runs[0].get("usage") or {})
        print(f"{name:<26} {kind:<8} visible={vis} reasoning={rea} prompt={u.get('prompt_tokens')} "
              f"msg_target={target} msg_got={calibrated_to} "
              f"cached={(u.get('prompt_tokens_details') or {}).get('cached_tokens')} "
              f"compl={u.get('completion_tokens')} finish={runs[0].get('finish')} "
              f"ttft={runs[0].get('ttft_ms')} total={runs[0].get('total_ms')}")

    st_after = json.load(urllib.request.urlopen(base + "/status", timeout=20))
    out["scheduler_after"] = st_after.get("scheduler")
    byte_probes = [k for k, v in out["probes"].items() if v["byte_claim"]]
    vis_ok = sum(1 for k in byte_probes if out["probes"][k]["visible_output_reproducible"] is True)
    rea_ok = sum(1 for k in byte_probes if out["probes"][k]["reasoning_reproducible"] is True)
    vis_bad = [k for k in byte_probes if out["probes"][k]["visible_output_reproducible"] is False]
    out["summary"] = {
        "probes": len(out["probes"]), "byte_claim_probes": byte_probes,
        "byte_probes_visible_reproducible": vis_ok, "byte_probes_visible_non_reproducible": vis_bad,
        "byte_probes_reasoning_reproducible": rea_ok,
        "timing_probes": [k for k, v in out["probes"].items() if not v["byte_claim"]],
    }
    print(f"\nbyte-claim probes: {len(byte_probes)}; visible output reproduces on {vis_ok}, "
          f"reasoning on {rea_ok}")
    if vis_bad:
        print(f"NON-REPRODUCIBLE visible output among byte probes: {', '.join(vis_bad)}")
    print(f"timing probes (usage/latency only, no byte claim): {len(out['summary']['timing_probes'])}")
    print("(a byte probe whose visible output does not reproduce cannot support a cross-version byte "
          "claim; reasoning hashes are reported separately because 1.7.1 shifts reasoning length, so "
          "their moving is expected and is not itself an output change)")
    text = json.dumps(out, indent=1)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"wrote {a.out} ({len(text):,} chars)")
    else:
        print(text)


if __name__ == "__main__":
    main()
