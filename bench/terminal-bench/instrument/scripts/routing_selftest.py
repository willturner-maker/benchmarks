#!/usr/bin/env python3
"""One-request routing self-test: does litellm + api_base deliver the PINNED model id?

Usage: routing_selftest.py <pinned-model-id> [base-url]

Why: Harbor's split_provider_model_name() treats the first "/"-separated component of the model
string as a provider, so an HF-style served id ("ISTA-DASLab/…") parses as provider "ista-daslab"
and litellm raises "LLM Provider NOT provided" — which voided an entire pilot. The working form is
`openai/<served id>`; this proves the prefix is stripped client-side by checking that the model the
engine reports back equals the pin exactly. Cheaper than rediscovering it with a wave of void trials.
"""

from __future__ import annotations

import sys

import litellm


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    mid = sys.argv[1]
    base = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000/v1"
    # No credential argument: this local endpoint is unauthenticated, and litellm accepts the call
    # without one (verified), so no key-shaped literal ever needs to exist in this file.
    try:
        r = litellm.completion(
            model=f"openai/{mid}", api_base=base,
            messages=[{"role": "user", "content": "Reply with exactly one word: OK"}],
            max_tokens=128, temperature=0,
        )
    except Exception as e:
        print(f"FATAL routing: {type(e).__name__}: {str(e)[:220]}")
        return 4
    det = getattr(r.usage, "completion_tokens_details", None)
    print(f"routing self-test: engine reported {r.model!r}; pin {mid!r} match={r.model == mid}")
    print(f"   tokens: {r.usage.completion_tokens} completion "
          f"({getattr(det, 'reasoning_tokens', 0) if det else 0} reasoning), "
          f"finish={r.choices[0].finish_reason}, content={ (r.choices[0].message.content or '')[:12]!r}")
    print("   note: thinking is billed as reasoning_tokens and returned in message.reasoning_content;")
    print("   a max_tokens below the thinking budget yields content='' (an empty agent action).")
    if r.model != mid:
        print("FATAL: the served model is not the pinned id — stop before spending a wave")
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
