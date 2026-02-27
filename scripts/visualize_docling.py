#!/usr/bin/env python3
"""Visualize Docling's element classification on a PDF.

Renders each page with colored bounding boxes showing how Docling
classified each region (table, form_area, text, section_header, etc.).

Output goes to dev_output/<filename>/ with:
  - page_N_annotated.png  -- PDF page with bounding boxes overlaid
  - elements.txt          -- text dump of all classified elements

Usage:
    uv run python scripts/visualize_docling.py /path/to/document.pdf
"""

import sys
from pathlib import Path

# Color map: Docling label -> (R, G, B, alpha)
_COLORS = {
    # Groups
    "form_area": (255, 0, 0),        # red
    "key_value_area": (255, 0, 0),   # red
    "section": (128, 128, 128),      # gray
    "list": (128, 128, 128),         # gray
    # Doc items
    "table": (0, 0, 255),            # blue
    "section_header": (255, 165, 0), # orange
    "title": (255, 165, 0),          # orange
    "text": (0, 180, 0),             # green
    "list_item": (0, 180, 0),        # green
    "form": (255, 0, 255),           # magenta
    "key_value_region": (255, 0, 255),
    "caption": (128, 128, 0),        # olive
    "page_header": (180, 180, 180),  # light gray
    "page_footer": (180, 180, 180),
}
_DEFAULT_COLOR = (100, 100, 100)


def _label_str(item: object) -> str:
    """Get a string label from a Docling item."""
    label = getattr(item, "label", None)
    if label is not None:
        return getattr(label, "value", str(label))
    return "unknown"


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/visualize_docling.py <pdf_path>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        sys.exit(1)

    # Output directory
    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / "dev_output" / pdf_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Parse with Docling to get element tree
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter, PdfFormatOption

    print(f"Parsing {pdf_path.name} with Docling...")
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF, InputFormat.IMAGE],
        format_options={InputFormat.PDF: PdfFormatOption()},
    )
    result = converter.convert(pdf_path, raises_on_error=False)
    doc = result.document

    # Step 2: Collect all elements with bounding boxes, grouped by page
    elements_by_page: dict[int, list[tuple[str, str, object]]] = {}

    def _collect(item: object, kind: str) -> None:
        prov = getattr(item, "prov", [])
        text = getattr(item, "text", "")
        label = _label_str(item)
        tag = f"{kind}:{label}"
        for p in prov:
            page_no = p.page_no
            elements_by_page.setdefault(page_no, []).append((tag, text, p.bbox))

    # Tables
    for t in doc.tables:
        _collect(t, "table")

    # Groups
    for g in doc.groups:
        _collect(g, "group")

    # Text items
    for t in doc.texts:
        _collect(t, "item")

    # Pictures
    for p in doc.pictures:
        _collect(p, "picture")

    # Key-value items
    for kv in doc.key_value_items:
        _collect(kv, "kv")

    # Form items
    for f in doc.form_items:
        _collect(f, "form")

    # Step 3: Render each page with pdfplumber and overlay boxes
    import pdfplumber
    from PIL import ImageDraw, ImageFont

    pdf = pdfplumber.open(pdf_path)
    resolution = 150
    elements_log: list[str] = []

    for page_idx, page in enumerate(pdf.pages):
        page_no = page_idx + 1
        page_elements = elements_by_page.get(page_no, [])

        # Get Docling page info for coordinate mapping
        docling_page = doc.pages.get(page_no)
        if docling_page:
            doc_w = docling_page.size.width
            doc_h = docling_page.size.height
        else:
            doc_w = page.width
            doc_h = page.height

        # Render page
        img = page.to_image(resolution=resolution).original
        img_w, img_h = img.size
        scale_x = img_w / doc_w
        scale_y = img_h / doc_h

        draw = ImageDraw.Draw(img, "RGBA")

        elements_log.append(f"\n{'='*60}")
        elements_log.append(f"PAGE {page_no}")
        elements_log.append(f"{'='*60}")

        for tag, text, bbox in page_elements:
            label_key = tag.split(":")[-1]
            color = _COLORS.get(label_key, _DEFAULT_COLOR)

            # Convert Docling bbox to image coordinates
            # bbox has l, t, r, b and coord_origin
            origin = getattr(bbox.coord_origin, "value", str(bbox.coord_origin))

            x0 = bbox.l * scale_x
            x1 = bbox.r * scale_x
            if origin == "BOTTOMLEFT":
                y0 = (doc_h - bbox.t) * scale_y
                y1 = (doc_h - bbox.b) * scale_y
                if y0 > y1:
                    y0, y1 = y1, y0
            else:  # TOPLEFT
                y0 = bbox.t * scale_y
                y1 = bbox.b * scale_y

            # Draw semi-transparent filled rect + border
            fill = color + (40,)
            draw.rectangle([x0, y0, x1, y1], fill=fill, outline=color, width=2)

            # Label in top-left corner
            label_text = tag
            draw.text((x0 + 2, y0 + 2), label_text, fill=color)

            # Log
            snippet = text[:80].replace("\n", " ") if text else ""
            elements_log.append(f"  [{tag}] ({bbox.l:.0f},{bbox.t:.0f})-({bbox.r:.0f},{bbox.b:.0f}) {snippet}")

        # Save annotated page
        out_path = out_dir / f"page_{page_no}_annotated.png"
        img.save(str(out_path))
        print(f"  Page {page_no}: {len(page_elements)} elements -> {out_path}")

    pdf.close()

    # Save element log
    log_path = out_dir / "elements.txt"
    log_path.write_text("\n".join(elements_log))
    print(f"\nElement log: {log_path}")
    print(f"Output dir:  {out_dir}")


if __name__ == "__main__":
    main()
