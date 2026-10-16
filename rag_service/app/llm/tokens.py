"""Exact token counting via the serving model's own tokenizer (spec §11.1).

No character heuristics, no tiktoken. POST /tokenize on the llama-server
embed instance (same BPE family as the corpus tokens); the response shape is
the one printed by the serving build and verified in artifacts/verification.md.
A missing 'tokens' key fails loud (§0.4) — never estimated.
"""
from __future__ import annotations

import hashlib
from collections import OrderedDict

import httpx

LRU_SIZE = 4096
_lru: OrderedDict[str, int] = OrderedDict()


async def count_tokens(client: httpx.AsyncClient, tokenize_url: str, text: str) -> int:
    """Exact token count, cached by content hash (§11.1 LRU, 4,096 entries)."""
    key = hashlib.sha256(text.encode("utf-8")).hexdigest()
    cached = _lru.get(key)
    if cached is not None:
        _lru.move_to_end(key)
        return cached

    r = await client.post(tokenize_url, json={"content": text})
    r.raise_for_status()
    data = r.json()
    tokens = data.get("tokens")
    if tokens is None:
        raise RuntimeError(
            f"tokenize response at {tokenize_url} has no 'tokens' key "
            f"(got keys {sorted(data)}) — record the real shape in "
            "artifacts/verification.md (§1.3 VERIFY) before adjusting"
        )
    n = len(tokens)
    _lru[key] = n
    _lru.move_to_end(key)
    while len(_lru) > LRU_SIZE:
        _lru.popitem(last=False)
    return n
