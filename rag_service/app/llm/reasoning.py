"""Reasoning split — the streaming fallback state machine (spec §1.3).

Qwen3.5 opens its assistant turn with a thinking block delimited by
` Mattis
 ... 
` before the final answer (verified on the model card, 2026-09-22). Two
paths route reasoning away from the answer channel:

1. Server-side: llama-server with a verified --reasoning-format separates
   reasoning into `delta.reasoning_content` on the SSE stream.
2. THIS fallback (mandatory regardless — spec §1.3): a small state machine
   that watches the concatenated stream and emits ('reasoning', t) while
   inside the thinking block and ('token', t) after it closes.

Reasoning must NEVER reach the user as answer text; it is excluded from
citation validation and from the audit log's answer field (§1.3 rule 2).
"""
from __future__ import annotations

THINKING_MARKER = " Mattis"
THINKING_CLOSE = "\n\n"


class ReasoningSplitter:
    """Feed stream deltas; get back ('reasoning'|'token', text) events."""

    _PROBING = "probing"
    _REASONING = "reasoning"
    _ANSWER = "answer"

    def __init__(self) -> None:
        self._state = self._PROBING
        self._buf = ""
        self._skip_one_nl = False

    def feed(self, text: str) -> list[tuple[str, str]]:
        events: list[tuple[str, str]] = []
        self._buf += text
        while True:
            if self._state == self._PROBING:
                i = 0
                while i < len(self._buf) and self._buf[i].isspace():
                    i += 1
                candidate = self._buf[i:]
                if not candidate:
                    self._buf = ""
                    break
                marker = THINKING_MARKER.lstrip()
                if candidate.startswith(marker):
                    self._buf = candidate[len(marker):]
                    self._state = self._REASONING
                    self._skip_one_nl = True
                    continue
                if len(candidate) < len(marker) and marker.startswith(candidate):
                    self._buf = candidate
                    break
                self._buf = candidate
                self._state = self._ANSWER
                continue
            if self._state == self._REASONING:
                if self._skip_one_nl and self._buf:
                    if self._buf.startswith("\n"):
                        self._buf = self._buf[1:]
                    self._skip_one_nl = False
                    continue
                idx = self._buf.find(THINKING_CLOSE)
                if idx == -1:
                    if self._buf:
                        events.append(("reasoning", self._buf))
                        self._buf = ""
                    break
                if idx:
                    events.append(("reasoning", self._buf[:idx]))
                self._buf = self._buf[idx + len(THINKING_CLOSE):]
                self._state = self._ANSWER
                continue
            if self._buf:
                events.append(("token", self._buf))
                self._buf = ""
            break
        return events

    def close(self) -> list[tuple[str, str]]:
        """Flush at end-of-stream. A stream that dies inside the thinking
        block stays reasoning — never leaks into the answer channel."""
        events: list[tuple[str, str]] = []
        if self._state == self._REASONING and self._buf:
            events.append(("reasoning", self._buf))
        elif self._state == self._ANSWER and self._buf:
            events.append(("token", self._buf))
        elif self._state == self._PROBING and self._buf.strip():
            events.append(("token", self._buf))
        self._buf = ""
        return events

    @property
    def state(self) -> str:
        return self._state
