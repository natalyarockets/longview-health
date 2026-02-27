#!/usr/bin/env python3
"""Test the full extraction pipeline on a real document.

Run from project root:
    uv run python scripts/test_extraction.py /path/to/document.pdf

Output goes to dev_output/<document-stem>/:
  - raw_markdown.md          -- Docling markdown output
  - page_N_regions.png       -- PDF pages with region bounding boxes + IDs
  - elements.txt             -- raw Docling elements with positions
  - regions.txt              -- region text content (what gets sent to extractors)
  - extraction_details.txt   -- per-region input/output details
  - results.txt              -- final extracted medical results
  - results.json             -- machine-readable results
"""

import json
import sys
import time
from datetime import date
from pathlib import Path

# Region colors: table=blue, content/section=green, skipped=gray
_REGION_COLORS = {
    "table": (0, 0, 255),
    "section": (0, 180, 0),
    "content": (0, 180, 0),
}
_DEFAULT_COLOR = (100, 100, 100)

# Element-level colors for raw Docling view
_ELEMENT_COLORS = {
    "form_area": (255, 0, 0),
    "key_value_area": (255, 0, 0),
    "table": (0, 0, 255),
    "section_header": (255, 165, 0),
    "title": (255, 165, 0),
    "text": (0, 180, 0),
    "list_item": (0, 180, 0),
    "page_header": (180, 180, 180),
    "page_footer": (180, 180, 180),
}


def _label_str(item: object) -> str:
    label = getattr(item, "label", None)
    if label is not None:
        return getattr(label, "value", str(label))
    return "unknown"


def _render_elements(doc, pdf_path: Path, out_dir: Path) -> None:
    """Render raw Docling elements (low-level view)."""
    import pdfplumber
    from PIL import ImageDraw

    elements_by_page: dict[int, list[tuple[str, str, object]]] = {}

    def _collect(item: object, kind: str) -> None:
        for p in getattr(item, "prov", []):
            text = getattr(item, "text", "")
            label = _label_str(item)
            tag = f"{kind}:{label}"
            elements_by_page.setdefault(p.page_no, []).append((tag, text, p.bbox))

    for t in doc.tables:
        _collect(t, "table")
    for g in doc.groups:
        _collect(g, "group")
    for t in doc.texts:
        _collect(t, "item")
    for p in doc.pictures:
        _collect(p, "picture")
    for kv in doc.key_value_items:
        _collect(kv, "kv")
    for f in doc.form_items:
        _collect(f, "form")

    elements_log: list[str] = []
    pdf = pdfplumber.open(pdf_path)

    for page_idx, page in enumerate(pdf.pages):
        page_no = page_idx + 1
        page_elements = elements_by_page.get(page_no, [])

        docling_page = doc.pages.get(page_no)
        doc_w = docling_page.size.width if docling_page else page.width
        doc_h = docling_page.size.height if docling_page else page.height

        elements_log.append(f"\n{'='*60}")
        elements_log.append(f"PAGE {page_no}")
        elements_log.append(f"{'='*60}")
        for tag, text, bbox in page_elements:
            snippet = text[:80].replace("\n", " ") if text else ""
            elements_log.append(f"  [{tag}] ({bbox.l:.0f},{bbox.t:.0f})-({bbox.r:.0f},{bbox.b:.0f}) {snippet}")

    pdf.close()
    (out_dir / "elements.txt").write_text("\n".join(elements_log))


def _render_regions(doc, regions, pdf_path: Path, out_dir: Path) -> None:
    """Render region bounding boxes on PDF pages with region IDs.

    Each region is drawn as a colored box with its ID number matching stdout.
    Table regions are blue, text/section regions are green.
    """
    import pdfplumber
    from PIL import ImageDraw, ImageFont

    pdf = pdfplumber.open(pdf_path)

    # Group regions by page
    regions_by_page: dict[int, list[tuple[int, object]]] = {}
    for i, r in enumerate(regions):
        regions_by_page.setdefault(r.page_no, []).append((i, r))

    for page_idx, page in enumerate(pdf.pages):
        page_no = page_idx + 1
        page_regions = regions_by_page.get(page_no, [])

        docling_page = doc.pages.get(page_no)
        doc_w = docling_page.size.width if docling_page else page.width
        doc_h = docling_page.size.height if docling_page else page.height

        img = page.to_image(resolution=150).original
        img_w, img_h = img.size
        scale_x = img_w / doc_w
        scale_y = img_h / doc_h

        draw = ImageDraw.Draw(img, "RGBA")

        for region_id, region in page_regions:
            color = _REGION_COLORS.get(region.label, _DEFAULT_COLOR)

            # Convert from BOTTOMLEFT coords to image coords
            x0 = region.bbox_l * scale_x
            x1 = region.bbox_r * scale_x
            y0 = (doc_h - region.bbox_t) * scale_y
            y1 = (doc_h - region.bbox_b) * scale_y
            if y0 > y1:
                y0, y1 = y1, y0

            # Draw box
            fill = color + (30,)
            draw.rectangle([x0, y0, x1, y1], fill=fill, outline=color, width=3)

            # Draw region ID label
            method = "TABLE" if region.table_item is not None else "LLM"
            label = f"[{region_id}] {region.label} -> {method}"
            # Background for readability
            text_bbox = draw.textbbox((x0 + 4, y0 + 2), label)
            draw.rectangle(text_bbox, fill=(255, 255, 255, 200))
            draw.text((x0 + 4, y0 + 2), label, fill=color)

        out_path = out_dir / f"page_{page_no}_regions.png"
        img.save(str(out_path))
        print(f"    Page {page_no}: {len(page_regions)} regions -> {out_path.name}")

    pdf.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/test_extraction.py <pdf_path>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        sys.exit(1)

    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / "dev_output" / pdf_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Parse with Docling
    from longview_health.extract import parser_chain

    print(f"Step 1: Parsing {pdf_path.name} with Docling...")
    t0 = time.perf_counter()
    conversion = parser_chain.parse_rich(pdf_path)
    parse_ms = (time.perf_counter() - t0) * 1000

    parsed = conversion.parsed
    print(f"  Parser: {parsed.parser_used}")
    print(f"  Pages: {parsed.page_count}")
    print(f"  Markdown: {len(parsed.markdown)} chars")
    print(f"  Docling element tree: {'yes' if conversion.docling_document else 'no'}")
    print(f"  Parse time: {parse_ms:.0f}ms")

    # Save raw markdown
    (out_dir / "raw_markdown.md").write_text(parsed.markdown)
    print(f"  Saved: raw_markdown.md")
    print()

    # Step 2: Group into spatial regions
    regions = []
    if conversion.docling_document:
        from longview_health.extract.region_grouper import group_regions

        regions = group_regions(conversion.docling_document)
        print(f"Step 2: Region grouping ({len(regions)} regions)")
        regions_lines: list[str] = []
        for i, r in enumerate(regions):
            method = "TABLE" if r.table_item is not None else "LLM"
            detail = ""
            if r.table_item is not None:
                data = getattr(r.table_item, "data", None)
                if data:
                    detail = f" ({data.num_rows}x{data.num_cols} grid)"
            else:
                detail = f" ({len(r.text)} chars)"

            print(f"  [{i}] page {r.page_no} {r.label} -> {method}{detail}")

            regions_lines.append(f"{'='*60}")
            regions_lines.append(f"REGION [{i}] page={r.page_no} label={r.label} -> {method}")
            regions_lines.append(f"bbox: l={r.bbox_l:.0f} t={r.bbox_t:.0f} r={r.bbox_r:.0f} b={r.bbox_b:.0f}")
            regions_lines.append(f"{'='*60}")
            regions_lines.append(r.text)
            regions_lines.append("")

        (out_dir / "regions.txt").write_text("\n".join(regions_lines))
        print()
    else:
        print("Step 2: No Docling element tree -- using legacy markdown parsing")
        print()

    # Step 3: Render annotated pages (bounding boxes with region IDs)
    if conversion.docling_document and regions:
        print("Step 3: Rendering region bounding boxes on pages...")
        _render_regions(conversion.docling_document, regions, pdf_path, out_dir)
        # Also save raw element view
        _render_elements(conversion.docling_document, pdf_path, out_dir)
        print(f"    Saved: elements.txt")
        print()

    # Step 4: Extraction (tables first, then combined LLM for text regions)
    from longview_health.extract import llm_extractor, result_merger, table_parser
    from longview_health.extract.table_parser import _detect_date

    result_date = _detect_date(parsed.markdown) or date(2025, 2, 21)

    print("Step 4: Extraction...")
    all_result_lists: list[list] = []
    region_details: list[str] = []
    t0 = time.perf_counter()

    if conversion.docling_document and regions:
        # 4a: Table regions (deterministic, instant)
        for i, region in enumerate(regions):
            if region.table_item is None:
                continue
            rt0 = time.perf_counter()
            region_results = table_parser.extract_from_table_item(
                table_item=region.table_item,
                doc_id=parsed.document_id,
                result_date=result_date,
                parser_used=parsed.parser_used,
            )
            region_ms = (time.perf_counter() - rt0) * 1000

            print(f"  [{i}] {region.label} (table): {len(region_results)} results in {region_ms:.0f}ms")
            for r in region_results:
                flag = " [ABNORMAL]" if r.result_value.is_abnormal else ""
                print(f"      -> {r.test_name}: {r.result_value.value} {r.result_value.unit or ''}{flag}")

            all_result_lists.append(region_results)

            region_details.append(f"{'='*60}")
            region_details.append(f"REGION [{i}] page={region.page_no} label={region.label} method=table")
            region_details.append(f"Time: {region_ms:.0f}ms  Results: {len(region_results)}")
            region_details.append(f"{'='*60}")
            region_details.append("")
            region_details.append("INPUT TEXT:")
            region_details.append("-" * 40)
            region_details.append(region.text)
            region_details.append("-" * 40)
            region_details.append("")
            region_details.append("EXTRACTED RESULTS:")
            if region_results:
                for r in region_results:
                    region_details.append(f"  {r.test_name}: {r.result_value.value} {r.result_value.unit or ''}")
                    region_details.append(f"    ref: {r.result_value.reference_low or ''} - {r.result_value.reference_high or ''}")
                    region_details.append(f"    abnormal: {r.result_value.is_abnormal}  extractor: {r.extractor_version}")
            else:
                region_details.append("  (none)")
            region_details.append("")
            region_details.append("")

        # 4b: Non-table regions combined into one LLM call
        text_regions = [(i, r) for i, r in enumerate(regions) if r.table_item is None and r.text.strip()]

        if text_regions:
            region_separator = "\n\n---\n\n"
            combined_text = region_separator.join(r.text.strip() for _, r in text_regions)
            region_ids = [str(i) for i, _ in text_regions]

            print(f"  [{','.join(region_ids)}] combined text (llm): {len(combined_text)} chars...")
            rt0 = time.perf_counter()
            llm_results = llm_extractor.extract_region(
                region_text=combined_text,
                doc_id=parsed.document_id,
                parser_used=parsed.parser_used,
                fallback_date=result_date,
            )
            region_ms = (time.perf_counter() - rt0) * 1000

            print(f"      {len(llm_results)} results in {region_ms:.0f}ms")
            for r in llm_results:
                flag = " [ABNORMAL]" if r.result_value.is_abnormal else ""
                print(f"      -> {r.test_name}: {r.result_value.value} {r.result_value.unit or ''}{flag}")

            all_result_lists.append(llm_results)

            region_details.append(f"{'='*60}")
            region_details.append(f"COMBINED LLM CALL (regions [{','.join(region_ids)}])")
            region_details.append(f"Time: {region_ms:.0f}ms  Results: {len(llm_results)}")
            region_details.append(f"{'='*60}")
            region_details.append("")
            region_details.append("INPUT TEXT SENT TO LLM:")
            region_details.append("-" * 40)
            region_details.append(combined_text)
            region_details.append("-" * 40)
            region_details.append("")
            region_details.append("EXTRACTED RESULTS:")
            if llm_results:
                for r in llm_results:
                    region_details.append(f"  {r.test_name}: {r.result_value.value} {r.result_value.unit or ''}")
                    region_details.append(f"    ref: {r.result_value.reference_low or ''} - {r.result_value.reference_high or ''}")
                    region_details.append(f"    abnormal: {r.result_value.is_abnormal}  extractor: {r.extractor_version}")
            else:
                region_details.append("  (none)")
            region_details.append("")
        else:
            print("  (no non-table text regions)")

        results = result_merger.merge(*all_result_lists)
    else:
        results = table_parser.extract(parsed=parsed, fallback_date=date(2025, 2, 21))

    extract_ms = (time.perf_counter() - t0) * 1000

    if region_details:
        (out_dir / "extraction_details.txt").write_text("\n".join(region_details))

    print()

    # Step 5: Display and save final results
    print("=" * 70)
    print(f"RESULTS ({len(results)} total)")
    print("=" * 70)
    results_lines: list[str] = [
        f"Total: {len(results)} results",
        f"Timing: parse={parse_ms:.0f}ms  extract={extract_ms:.0f}ms  total={parse_ms + extract_ms:.0f}ms",
        "",
    ]
    results_json = []
    for r in results:
        flag = " [ABNORMAL]" if r.result_value.is_abnormal else ""
        unit = r.result_value.unit or ""
        ref = ""
        if r.result_value.reference_low or r.result_value.reference_high:
            lo = r.result_value.reference_low or ""
            hi = r.result_value.reference_high or ""
            ref = f"  (ref: {lo}-{hi})"
        line1 = f"{r.test_name}: {r.result_value.value} {unit}{ref}{flag}"
        line2 = f"  extractor={r.extractor_version}  confidence={r.confidence.value}  date={r.result_date}"
        print(f"  {line1}")
        print(f"    {line2}")
        results_lines.append(line1)
        results_lines.append(line2)
        results_json.append({
            "test_name": r.test_name,
            "value": r.result_value.value,
            "unit": r.result_value.unit,
            "reference_low": r.result_value.reference_low,
            "reference_high": r.result_value.reference_high,
            "is_abnormal": r.result_value.is_abnormal,
            "category": r.category.value,
            "result_date": str(r.result_date),
            "extractor": r.extractor_version,
            "confidence": r.confidence.value,
        })

    (out_dir / "results.txt").write_text("\n".join(results_lines))
    (out_dir / "results.json").write_text(json.dumps(results_json, indent=2))

    print()
    print(f"Timing: parse={parse_ms:.0f}ms  extract={extract_ms:.0f}ms  total={parse_ms + extract_ms:.0f}ms")
    print()
    print(f"Output: {out_dir}/")
    print(f"  raw_markdown.md        -- Docling markdown")
    print(f"  page_*_regions.png     -- pages with region [ID] boxes matching stdout")
    print(f"  elements.txt           -- raw Docling elements")
    print(f"  regions.txt            -- region text content")
    print(f"  extraction_details.txt -- what was sent to each extractor + what came back")
    print(f"  results.txt/json       -- final results")


if __name__ == "__main__":
    main()
