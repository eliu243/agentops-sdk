from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from .config import config


@dataclass
class PolicyResult:
    allowed: bool
    label: str
    reason: str
    matches: List[str]


def _load_default_patterns() -> Tuple[List[str], List[str]]:
    substrings = [
        "password",
        "api_key",
        "secret key",
        "ssn",
        "credit card",
    ]
    regexes = [
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
        r"sk-[A-Za-z0-9]{20,}",        # Generic sk- style keys
        r"(?:\d[ -]*?){13,16}",       # CC-ish
    ]
    # Env override: comma-separated substrings
    env_forbidden = os.getenv("AGENTOPS_FORBIDDEN")
    if env_forbidden:
        for s in env_forbidden.split(","):
            s = s.strip()
            if s:
                substrings.append(s)
    return substrings, regexes


def _find_matches(text: str, substrings: Iterable[str], regexes: Iterable[str]) -> List[str]:
    lowered = text.lower()
    found: List[str] = []
    for s in substrings:
        if s.lower() in lowered:
            found.append(s)
    for pattern in regexes:
        try:
            if re.search(pattern, text, flags=re.IGNORECASE):
                found.append(f"re:{pattern}")
        except re.error:
            continue
    return found


def evaluate_text(text: Optional[str], direction: str, extra_forbidden: Optional[Iterable[str]] = None) -> PolicyResult:
    if not text:
        return PolicyResult(True, label="clean", reason="empty_or_none", matches=[])
    substrings, regexes = _load_default_patterns()
    if extra_forbidden:
        for s in extra_forbidden:
            s = (s or "").strip()
            if s:
                substrings.append(s)
    matches = _find_matches(text, substrings, regexes)
    if matches:
        return PolicyResult(
            allowed=False,
            label="unauthorized_content",
            reason=f"{direction}_forbidden_content",
            matches=matches,
        )
    return PolicyResult(True, label="clean", reason="no_matches", matches=[])


def _llm_analyze(text: str, direction: str) -> Optional[PolicyResult]:
    try:
        from openai import OpenAI  # optional dependency
    except Exception:
        # OpenAI SDK not installed
        print("WARNING: OpenAI SDK not installed, skipping LLM policy check")
        return PolicyResult(True, label="llm_skipped", reason=f"{direction}_llm_skipped:missing_openai", matches=[])

    try:
        # Attempt client creation (may fail if API key missing)
        client = OpenAI()
        model = config.llm_policy_model or "gpt-4o-mini"
        prompt = (
            "Analyze this agent message for policy violations and respond with JSON only.\n\n"
            f"DIRECTION: {direction}\n"
            f"MESSAGE: {text}\n\n"
            "Fields: {\"has_violation\": bool, \"violation_type\": str|null, \"severity\": \"low|medium|high|critical\"|null, \"explanation\": str, \"confidence\": number}"
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a content moderation system. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=250,
            response_format={"type": "json_object"},
        )
        import json as _json

        content = resp.choices[0].message.content
        data = _json.loads(content)
        if data.get("has_violation"):
            vt = data.get("violation_type") or "llm_violation"
            sev = data.get("severity") or "medium"
            expl = data.get("explanation") or ""
            conf = data.get("confidence")
            label = f"llm_{vt}"
            reason = f"{direction}_llm_policy:{sev}:{conf}"
            return PolicyResult(False, label=label, reason=reason, matches=[expl])
        return PolicyResult(True, label="llm_clean", reason="no_violation", matches=[])
    except Exception as e:
        # Any runtime error -> mark as skipped with reason
        print(f"Runtime error: {e}")
        msg = str(e)
        return PolicyResult(True, label="llm_skipped", reason=f"{direction}_llm_skipped:error", matches=[msg[:180]])


def evaluate(text: Optional[str], direction: str, extra_forbidden: Optional[Iterable[str]] = None) -> PolicyResult:
    # 1) Lightweight keyword/regex check
    basic = evaluate_text(text, direction=direction, extra_forbidden=extra_forbidden)
    # 2) If keyword violation and configured to run LLM anyway, combine results
    if not basic.allowed:
        if config.enable_llm_policy and config.llm_policy_after_keyword and text:
            llm_result = _llm_analyze(text, direction)
            if llm_result is not None:
                # Combine: always blocked, but expose both sources
                combined_label = f"{basic.label}|{llm_result.label}"
                combined_reason = f"{basic.reason}|{llm_result.reason}"
                combined_matches = list(basic.matches) + list(llm_result.matches)
                return PolicyResult(False, combined_label, combined_reason, combined_matches)
        return basic
    # 3) Optional LLM policy check if no keyword violation
    if config.enable_llm_policy and text:
        llm_result = _llm_analyze(text, direction)
        if llm_result is not None:
            return llm_result
    return basic


