"""Section router -- classifies document regions for smart extraction.

Walks Docling's element tree (tables, groups, text items) and classifies
each section as TABLE, FORM, or UNSTRUCTURED. This allows the extraction
pipeline to dispatch each section to the most appropriate extractor.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Header keywords that identify a form section as containing lab results
_FORM_HEADERS = frozenset({
    "tests", "test", "results", "result", "flag",
    "units", "unit", "reference interval", "reference range", "lab",
})


class SectionType(Enum):
    TABLE = "table"
    FORM = "form"
    UNSTRUCTURED = "unstructured"


@dataclass(frozen=True)
class ClassifiedSection:
    """A classified document region ready for extraction."""

    section_type: SectionType
    table_item: Any | None = None
    texts: list[str] = field(default_factory=list)


def _has_lab_headers(texts: list[str]) -> bool:
    """Check if text items contain recognizable lab report headers."""
    for t in texts:
        if t.lower().strip() in _FORM_HEADERS:
            return True
    return False


def classify(docling_doc: Any) -> list[ClassifiedSection]:
    """Classify document sections by type using Docling's element tree.

    Walks tables, groups (form areas), and remaining text to produce
    a list of ClassifiedSection objects for dispatch to extractors.

    Args:
        docling_doc: A Docling DoclingDocument instance.

    Returns:
        List of ClassifiedSection, one per identified region.
    """
    sections: list[ClassifiedSection] = []
    covered_refs: set[str] = set()

    # 1. Tables -> TABLE sections
    for table_item in docling_doc.tables:
        sections.append(ClassifiedSection(
            section_type=SectionType.TABLE,
            table_item=table_item,
        ))
        covered_refs.add(table_item.self_ref)

    # 2. Form areas with lab headers -> FORM sections
    for group in docling_doc.groups:
        label_value = getattr(group.label, "value", str(group.label))
        if label_value not in ("form_area", "key_value_area"):
            continue

        child_texts: list[str] = []
        for child_ref in group.children:
            try:
                item = child_ref.resolve(docling_doc)
            except Exception:
                continue
            text = getattr(item, "text", None)
            if text is not None:
                # Preserve empty strings to maintain column alignment
                child_texts.append(text.strip())
                covered_refs.add(getattr(item, "self_ref", ""))

        if child_texts and _has_lab_headers(child_texts):
            sections.append(ClassifiedSection(
                section_type=SectionType.FORM,
                texts=child_texts,
            ))
            covered_refs.add(group.self_ref)

    # 3. Remaining uncovered text -> UNSTRUCTURED section
    uncovered: list[str] = []
    for text_item in docling_doc.texts:
        if text_item.self_ref not in covered_refs:
            text = text_item.text.strip()
            if text:
                uncovered.append(text)

    if uncovered:
        sections.append(ClassifiedSection(
            section_type=SectionType.UNSTRUCTURED,
            texts=uncovered,
        ))

    logger.info(
        "Classified %d sections: %s",
        len(sections),
        ", ".join(f"{s.section_type.value}" for s in sections),
    )

    return sections
