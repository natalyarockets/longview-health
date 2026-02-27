"""Region grouper -- spatial clustering of Docling elements.

Groups Docling's flat list of positioned elements into logical regions
using bounding box proximity and section headers as boundaries. Each
region becomes a focused chunk for LLM extraction.

Docling tells us WHERE things are (bounding boxes, element types).
The region grouper clusters them spatially. The LLM tells us WHAT
they mean.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Labels to exclude from content regions (not useful for extraction)
_SKIP_LABELS = frozenset({"page_header", "page_footer"})

# Y-gap threshold (in Docling coordinate units) that triggers a new region.
# Typical line spacing is 8-16 units; 30+ indicates a visual break.
_Y_GAP_THRESHOLD = 30.0


@dataclass
class DocumentRegion:
    """A spatial region of a document page, ready for LLM extraction."""

    page_no: int
    label: str  # "table", "section", or inferred from content
    text: str  # concatenated text in reading order
    bbox_l: float = 0.0
    bbox_t: float = 0.0
    bbox_r: float = 0.0
    bbox_b: float = 0.0
    table_item: Any | None = None  # Docling TableItem if this is a table region


@dataclass
class _Element:
    """Internal: a positioned element for sorting and grouping."""

    page_no: int
    y_top: float  # top of element (higher = higher on page)
    y_bottom: float
    x_left: float
    x_right: float
    label: str
    text: str
    is_section_header: bool = False
    raw_item: Any = None


def _collect_elements(docling_doc: Any) -> list[_Element]:
    """Extract positioned elements from a Docling document."""
    elements: list[_Element] = []

    for text_item in docling_doc.texts:
        label = getattr(text_item.label, "value", str(text_item.label))
        if label in _SKIP_LABELS:
            continue

        text = text_item.text.strip()
        if not text:
            continue

        for prov in text_item.prov:
            origin = getattr(prov.bbox.coord_origin, "value", "BOTTOMLEFT")

            if origin == "BOTTOMLEFT":
                # In BOTTOMLEFT coords, t > b (top is higher y)
                y_top = prov.bbox.t
                y_bottom = prov.bbox.b
            else:
                y_top = prov.bbox.t
                y_bottom = prov.bbox.b

            elements.append(_Element(
                page_no=prov.page_no,
                y_top=y_top,
                y_bottom=y_bottom,
                x_left=prov.bbox.l,
                x_right=prov.bbox.r,
                label=label,
                text=text,
                is_section_header=(label == "section_header"),
            ))

    return elements


def _group_into_regions(elements: list[_Element]) -> list[DocumentRegion]:
    """Group sorted elements into regions by section headers and y-gaps."""
    if not elements:
        return []

    # Sort by page, then top-to-bottom (descending y in BOTTOMLEFT coords)
    elements.sort(key=lambda e: (e.page_no, -e.y_top, e.x_left))

    regions: list[DocumentRegion] = []
    current_texts: list[str] = []
    current_page = elements[0].page_no
    current_label = "content"
    prev_y_bottom = elements[0].y_top
    bbox_l = float("inf")
    bbox_t = -float("inf")
    bbox_r = -float("inf")
    bbox_b = float("inf")

    def _flush() -> None:
        if current_texts:
            regions.append(DocumentRegion(
                page_no=current_page,
                label=current_label,
                text="\n".join(current_texts),
                bbox_l=bbox_l,
                bbox_t=bbox_t,
                bbox_r=bbox_r,
                bbox_b=bbox_b,
            ))

    for elem in elements:
        # New page = new region
        if elem.page_no != current_page:
            _flush()
            current_texts = []
            current_page = elem.page_no
            current_label = "content"
            prev_y_bottom = elem.y_top
            bbox_l = float("inf")
            bbox_t = -float("inf")
            bbox_r = -float("inf")
            bbox_b = float("inf")

        # Section header = new region
        if elem.is_section_header:
            _flush()
            current_texts = []
            current_label = "section"
            prev_y_bottom = elem.y_top
            bbox_l = float("inf")
            bbox_t = -float("inf")
            bbox_r = -float("inf")
            bbox_b = float("inf")

        # Large y-gap = new region
        y_gap = prev_y_bottom - elem.y_top  # positive = gap between elements
        if current_texts and y_gap > _Y_GAP_THRESHOLD:
            _flush()
            current_texts = []
            current_label = "content"
            bbox_l = float("inf")
            bbox_t = -float("inf")
            bbox_r = -float("inf")
            bbox_b = float("inf")

        current_texts.append(elem.text)
        prev_y_bottom = elem.y_bottom
        bbox_l = min(bbox_l, elem.x_left)
        bbox_t = max(bbox_t, elem.y_top)
        bbox_r = max(bbox_r, elem.x_right)
        bbox_b = min(bbox_b, elem.y_bottom)

    _flush()
    return regions


def group_regions(docling_doc: Any) -> list[DocumentRegion]:
    """Group a Docling document's elements into spatial regions.

    Tables get their own region. Text elements are grouped by section
    headers and y-gaps. Page headers/footers are excluded.

    Args:
        docling_doc: A Docling DoclingDocument instance.

    Returns:
        List of DocumentRegion, one per logical region.
    """
    regions: list[DocumentRegion] = []

    # 1. Tables are always their own region
    for table_item in docling_doc.tables:
        page_no = table_item.prov[0].page_no if table_item.prov else 1
        bbox = table_item.prov[0].bbox if table_item.prov else None

        # Build text representation from the table's markdown export
        text = ""
        data = getattr(table_item, "data", None)
        if data:
            for row_idx in range(data.num_rows):
                row_cells = []
                for col_idx in range(data.num_cols):
                    cell_text = ""
                    for cell in data.table_cells:
                        if cell.start_row_offset_idx == row_idx and cell.start_col_offset_idx == col_idx:
                            cell_text = cell.text.strip()
                            break
                    row_cells.append(cell_text)
                text += " | ".join(row_cells) + "\n"

        regions.append(DocumentRegion(
            page_no=page_no,
            label="table",
            text=text.strip(),
            bbox_l=bbox.l if bbox else 0,
            bbox_t=bbox.t if bbox else 0,
            bbox_r=bbox.r if bbox else 0,
            bbox_b=bbox.b if bbox else 0,
            table_item=table_item,
        ))

    # 2. Group text elements by section headers and y-gaps
    elements = _collect_elements(docling_doc)
    text_regions = _group_into_regions(elements)
    regions.extend(text_regions)

    # Sort all regions by page, then top-to-bottom
    regions.sort(key=lambda r: (r.page_no, -r.bbox_t))

    logger.info(
        "Grouped into %d regions: %s",
        len(regions),
        ", ".join(f"{r.label}({len(r.text)}ch)" for r in regions),
    )

    return regions
