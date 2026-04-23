from __future__ import annotations

import io
from typing import Any

ROLE_COLORS: dict[str, tuple[int, int, int]] = {
    "button": (66, 133, 244),
    "text": (52, 168, 83),
    "input": (251, 188, 4),
    "link": (255, 109, 1),
    "image": (171, 71, 188),
    "menu": (0, 172, 193),
    "window": (120, 144, 156),
    "dialog": (255, 167, 38),
    "tab": (141, 110, 99),
    "checkbox": (0, 150, 136),
    "radio": (233, 30, 99),
    "slider": (63, 81, 181),
    "scroll": (158, 158, 158),
    "table": (121, 85, 72),
    "list": (96, 125, 139),
}

DEFAULT_COLOR = (33, 33, 33)


def _role_color(role: str | None) -> tuple[int, int, int]:
    if role and role.lower() in ROLE_COLORS:
        return ROLE_COLORS[role.lower()]
    return DEFAULT_COLOR


def ocr_extract(image_bytes: bytes) -> list[dict[str, Any]]:
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return []

    try:
        image = Image.open(io.BytesIO(image_bytes))
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        results = []
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            if not text:
                continue
            conf = float(data["conf"][i])
            if conf < 0:
                continue
            results.append({
                "text": text,
                "x": int(data["left"][i]),
                "y": int(data["top"][i]),
                "width": int(data["width"][i]),
                "height": int(data["height"][i]),
                "confidence": round(conf / 100.0, 3),
            })
        return results
    except Exception:
        return []


def annotate_screenshot(image_bytes: bytes, elements: list[dict[str, Any]]) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except Exception:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        except Exception:
            font = ImageFont.load_default()

    for elem in elements:
        frame = elem.get("frame")
        if not frame:
            continue
        x = int(frame.get("x", 0))
        y = int(frame.get("y", 0))
        w = int(frame.get("width", 0))
        h = int(frame.get("height", 0))
        if w <= 0 or h <= 0:
            continue

        color = _role_color(elem.get("role"))
        index = elem.get("index", elem.get("element_index", ""))
        label = str(index)

        fill_color = color + (50,)
        outline_color = color + (200,)
        draw.rectangle([x, y, x + w, y + h], fill=fill_color, outline=outline_color, width=2)

        text_bbox = font.getbbox(label) if hasattr(font, "getbbox") else (0, 0, len(label) * 9, 14)
        tw = text_bbox[2] - text_bbox[0] + 8
        th = text_bbox[3] - text_bbox[1] + 4
        label_y = max(0, y - th - 2)
        draw.rectangle([x, label_y, x + tw, label_y + th], fill=color + (220,))
        draw.text((x + 4, label_y + 2), label, fill=(255, 255, 255, 255), font=font)

    composite = Image.alpha_composite(image, overlay).convert("RGB")
    buf = io.BytesIO()
    composite.save(buf, format="PNG")
    return buf.getvalue()


def diff_screenshots(before_bytes: bytes, after_bytes: bytes, threshold: float = 5.0) -> dict[str, Any]:
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        return {"changed": False, "regions": [], "diff_image": b""}

    before_img = Image.open(io.BytesIO(before_bytes)).convert("RGB")
    after_img = Image.open(io.BytesIO(after_bytes)).convert("RGB")

    if before_img.size != after_img.size:
        after_img = after_img.resize(before_img.size)

    before_arr = np.array(before_img, dtype=np.int16)
    after_arr = np.array(after_img, dtype=np.int16)
    diff = np.abs(before_arr - after_arr)
    changed_mask = np.any(diff > 0, axis=2)

    total_pixels = changed_mask.size
    changed_pixels = int(np.sum(changed_mask))
    overall_pct = (changed_pixels / total_pixels * 100) if total_pixels > 0 else 0.0

    if overall_pct < threshold:
        return {"changed": False, "regions": [], "diff_image": b"", "change_percent": round(overall_pct, 2)}

    block_size = 64
    regions = []
    h, w = changed_mask.shape
    for by in range(0, h, block_size):
        for bx in range(0, w, block_size):
            block = changed_mask[by:by + block_size, bx:bx + block_size]
            block_total = block.size
            block_changed = int(np.sum(block))
            pct = (block_changed / block_total * 100) if block_total > 0 else 0.0
            if pct >= threshold:
                regions.append({
                    "x": int(bx),
                    "y": int(by),
                    "width": min(block_size, w - bx),
                    "height": min(block_size, h - by),
                    "percentage": round(pct, 1),
                })

    diff_visual = np.zeros_like(after_arr, dtype=np.uint8)
    diff_visual[changed_mask] = after_arr[changed_mask].astype(np.uint8)
    diff_img = Image.fromarray(diff_visual)
    buf = io.BytesIO()
    diff_img.save(buf, format="PNG")

    return {
        "changed": True,
        "regions": regions,
        "diff_image": buf.getvalue(),
        "change_percent": round(overall_pct, 2),
    }


def describe_elements(elements: list[dict[str, Any]]) -> str:
    if not elements:
        return "No UI elements detected."

    role_counts: dict[str, int] = {}
    labels: list[str] = []
    for elem in elements:
        role = (elem.get("role") or "unknown").lower()
        role_counts[role] = role_counts.get(role, 0) + 1
        label = elem.get("label") or elem.get("title") or ""
        if label and len(labels) < 20:
            labels.append(f"{role} '{label}'")

    parts = [f"{count} {role}{'s' if count > 1 else ''}" for role, count in sorted(role_counts.items())]
    summary = f"Visible elements: {', '.join(parts)}."

    if labels:
        summary += " Including: " + ", ".join(labels)
        if len(labels) >= 20:
            summary += ", ..."

    return summary
