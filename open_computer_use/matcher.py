"""Element matching engine — finds UI elements from natural language descriptions."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

ROLE_KEYWORDS: dict[str, set[str]] = {
    "button": {"button", "btn"},
    "menu": {"menu", "dropdown"},
    "field": {"field", "textfield", "text field", "input", "textbox", "text box", "entry"},
    "tab": {"tab", "tabpanel"},
    "link": {"link", "hyperlink", "anchor"},
    "checkbox": {"checkbox", "check box", "toggle"},
    "radio": {"radio", "radio button"},
    "slider": {"slider", "range"},
    "scroll": {"scroll", "scrollbar", "scroll bar"},
    "table": {"table", "grid"},
    "list": {"list"},
    "dialog": {"dialog", "modal", "popup", "alert"},
    "window": {"window", "pane", "panel"},
    "image": {"image", "img", "picture", "icon"},
    "label": {"label", "heading", "caption"},
}

ROLE_ALIASES: dict[str, str] = {}
for _canonical, _aliases in ROLE_KEYWORDS.items():
    for _alias in _aliases:
        ROLE_ALIASES[_alias] = _canonical


@dataclass
class ParsedDescription:
    tokens: list[str]
    quoted_phrases: list[str]
    role_hint: str | None


def parse_description(description: str) -> ParsedDescription:
    description = description.strip()
    if not description:
        return ParsedDescription(tokens=[], quoted_phrases=[], role_hint=None)

    quoted_phrases: list[str] = re.findall(r'"([^"]+)"|\'([^\']+)\'', description)
    quoted_phrases = [q[0] or q[1] for q in quoted_phrases]

    cleaned = re.sub(r'"[^"]*"|\'[^\']*\'', ' ', description)
    raw_tokens = re.split(r'[\s,;|]+', cleaned)
    tokens: list[str] = []
    role_hint: str | None = None
    for token in raw_tokens:
        token_lower = token.lower().strip()
        if not token_lower:
            continue
        tokens.append(token_lower)
        if role_hint is None and token_lower in ROLE_ALIASES:
            role_hint = ROLE_ALIASES[token_lower]

    return ParsedDescription(tokens=tokens, quoted_phrases=quoted_phrases, role_hint=role_hint)


@dataclass
class ElementMatch:
    element_index: str
    role: str | None
    title: str | None
    frame: dict[str, float] | None
    score: float
    source: str
    app: str | None = None
    ocr_text: str | None = None


def _score_element(
    parsed: ParsedDescription,
    element_index: str,
    role: str | None,
    title: str | None,
    frame: dict[str, float] | None,
    enabled: bool = True,
) -> float:
    score = 0.0

    if parsed.role_hint and role and parsed.role_hint == role.lower():
        score += 30

    title_lower = (title or "").lower()

    for token in parsed.tokens:
        if token in ROLE_ALIASES:
            continue
        if token in title_lower:
            score += 20

    if parsed.tokens:
        non_role_tokens = [t for t in parsed.tokens if t not in ROLE_ALIASES]
        if non_role_tokens and all(t in title_lower for t in non_role_tokens):
            score += 25

    for phrase in parsed.quoted_phrases:
        phrase_lower = phrase.lower()
        if phrase_lower in title_lower:
            score += 40

    if enabled:
        score += 5

    if frame:
        w = frame.get("width", 0)
        h = frame.get("height", 0)
        if w > 0 and h > 0:
            score += 10

    return score


def _score_ocr(
    parsed: ParsedDescription,
    text: str,
    confidence: float,
) -> float:
    score = 0.0
    text_lower = text.lower()

    for token in parsed.tokens:
        if token in ROLE_ALIASES:
            continue
        if token in text_lower:
            score += 20

    if parsed.tokens:
        non_role_tokens = [t for t in parsed.tokens if t not in ROLE_ALIASES]
        if non_role_tokens and all(t in text_lower for t in non_role_tokens):
            score += 25

    for phrase in parsed.quoted_phrases:
        phrase_lower = phrase.lower()
        if phrase_lower in text_lower:
            score += 40

    score += confidence * 10

    return score


def find_elements(
    description: str,
    elements: list[dict[str, Any]] | None = None,
    ocr_results: list[dict[str, Any]] | None = None,
    match_strategy: str = "combined",
    max_results: int = 5,
    min_score: float = 15.0,
) -> list[ElementMatch]:
    parsed = parse_description(description)
    if not parsed.tokens and not parsed.quoted_phrases:
        return []

    use_a11y = match_strategy in ("accessibility", "combined", "auto")
    use_ocr = match_strategy in ("ocr", "combined", "auto")

    matches: list[ElementMatch] = []

    if use_a11y and elements:
        for elem in elements:
            idx = str(elem.get("element_index", elem.get("index", "")))
            role = elem.get("role")
            title = elem.get("title") or elem.get("label")
            frame = elem.get("frame")
            app = elem.get("app")
            enabled = elem.get("enabled", True)

            score = _score_element(parsed, idx, role, title, frame, enabled=enabled)
            if score >= min_score:
                matches.append(ElementMatch(
                    element_index=idx,
                    role=role,
                    title=title,
                    frame=frame,
                    score=score,
                    source="accessibility",
                    app=app,
                ))

    if use_ocr and ocr_results:
        for ocr_item in ocr_results:
            text = ocr_item.get("text", "")
            confidence = float(ocr_item.get("confidence", 0.5))
            x = int(ocr_item.get("x", 0))
            y = int(ocr_item.get("y", 0))
            w = int(ocr_item.get("width", 0))
            h = int(ocr_item.get("height", 0))

            score = _score_ocr(parsed, text, confidence)
            if score >= min_score:
                matches.append(ElementMatch(
                    element_index="",
                    role=None,
                    title=text,
                    frame={
                        "x": float(x),
                        "y": float(y),
                        "width": float(w),
                        "height": float(h),
                        "center_x": float(x + w // 2),
                        "center_y": float(y + h // 2),
                    },
                    score=score,
                    source="ocr",
                    ocr_text=text,
                ))

    matches.sort(key=lambda m: m.score, reverse=True)

    seen: set[tuple[float, float]] = set()
    deduped: list[ElementMatch] = []
    for match in matches:
        if match.frame:
            cx = match.frame.get("center_x", 0)
            cy = match.frame.get("center_y", 0)
            key = (round(cx, 1), round(cy, 1))
        else:
            key = (match.score, 0)
        if key not in seen:
            seen.add(key)
            deduped.append(match)

    return deduped[:max_results]


def match_center(match: ElementMatch) -> tuple[int, int]:
    if not match.frame:
        raise RuntimeError("Matched element has no frame/coordinates.")
    return int(round(match.frame["center_x"])), int(round(match.frame["center_y"]))
