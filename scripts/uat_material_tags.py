"""Generate development/UAT-only Material Tag QR artifacts."""

import base64
import html
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import qrcode

from app.services.weighing import parse_material_tag


@dataclass(frozen=True)
class UatMaterialTag:
    material_code: str
    material_name: str
    container_identity: str
    payload: str


UAT_MATERIAL_TAGS = (
    UatMaterialTag(
        material_code="MOCK-RM001",
        material_name="Mock Raw Material 01",
        container_identity="UAT-CONTAINER-RM001",
        payload=(
            "07/08/2026|UAT-PO-MATERIAL|10|MOCK-RM001|UAT-DN-RM001|"
            "UAT-CONTAINER-RM001|UAT-SUPPLIER|UAT ONLY|UAT-WH|UAT-LOC|UAT-SHELF"
        ),
    ),
    UatMaterialTag(
        material_code="MOCK-RM002",
        material_name="Mock Raw Material 02",
        container_identity="UAT-CONTAINER-RM002",
        payload=(
            "07/08/2026|UAT-PO-MATERIAL|20|MOCK-RM002|UAT-DN-RM002|"
            "UAT-CONTAINER-RM002|UAT-SUPPLIER|UAT ONLY|UAT-WH|UAT-LOC|UAT-SHELF"
        ),
    ),
)


def _png_bytes(payload):
    image = qrcode.make(payload).convert("RGB")
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def generate_uat_material_tag_sheet(output_directory, *, uat_enabled):
    """Create an idempotent standalone UAT sheet without database writes."""
    if not uat_enabled:
        raise RuntimeError("UAT Material Tag generation is disabled outside development/UAT.")

    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)
    cards = []
    for tag in UAT_MATERIAL_TAGS:
        parsed = parse_material_tag(tag.payload)
        if parsed.material_code != tag.material_code:
            raise RuntimeError("UAT Material Tag definition does not match its material.")
        image_bytes = _png_bytes(tag.payload)
        image_name = f"{tag.material_code}.png"
        (output_path / image_name).write_bytes(image_bytes)
        encoded_image = base64.b64encode(image_bytes).decode("ascii")
        cards.append(
            f"""
            <article class="tag-card">
              <h2>UAT ONLY — {html.escape(tag.material_code)}</h2>
              <p><strong>Material:</strong> {html.escape(tag.material_name)}</p>
              <p><strong>Container:</strong> {html.escape(tag.container_identity)}</p>
              <img src="data:image/png;base64,{encoded_image}"
                   alt="QR code for {html.escape(tag.material_code)}">
              <p class="payload"><strong>Exact QR payload:</strong><br>
                {html.escape(tag.payload)}
              </p>
            </article>
            """
        )

    sheet = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>UAT Material Tags</title>
  <style>
    body {{ font-family: sans-serif; margin: 24px; color: #111; }}
    .notice {{ padding: 12px; border: 2px solid #b00020; margin-bottom: 20px; }}
    .tags {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }}
    .tag-card {{ border: 1px solid #777; padding: 18px; break-inside: avoid; }}
    img {{ display: block; width: min(100%, 360px); image-rendering: pixelated; }}
    .payload {{ overflow-wrap: anywhere; font-family: monospace; font-size: 12px; }}
    @media print {{ body {{ margin: 8mm; }} .tags {{ grid-template-columns: 1fr 1fr; }} }}
  </style>
</head>
<body>
  <h1>UAT Material Tag QR Sheet</h1>
  <p class="notice"><strong>UAT ONLY.</strong>
    Scan these codes only in the approved development/UAT environment.
  </p>
  <section class="tags">{''.join(cards)}</section>
</body>
</html>
"""
    sheet_path = output_path / "index.html"
    sheet_path.write_text(sheet, encoding="utf-8")
    return sheet_path
