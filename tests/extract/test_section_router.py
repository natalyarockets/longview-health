"""Tests for section router."""

from unittest.mock import MagicMock

from longview_health.extract.section_router import (
    ClassifiedSection,
    SectionType,
    _has_lab_headers,
    classify,
)


class TestHasLabHeaders:
    def test_recognizes_tests_header(self) -> None:
        assert _has_lab_headers(["TESTS", "some value"]) is True

    def test_recognizes_results_header(self) -> None:
        assert _has_lab_headers(["RESULTS"]) is True

    def test_recognizes_reference_interval(self) -> None:
        assert _has_lab_headers(["REFERENCE INTERVAL"]) is True

    def test_case_insensitive(self) -> None:
        assert _has_lab_headers(["tests", "Results", "FLAG"]) is True

    def test_no_headers_returns_false(self) -> None:
        assert _has_lab_headers(["John Doe", "2024-01-15"]) is False

    def test_empty_returns_false(self) -> None:
        assert _has_lab_headers([]) is False


def _make_text_item(text: str, self_ref: str, parent_ref: str | None = None) -> MagicMock:
    """Create a mock Docling text item."""
    item = MagicMock()
    item.text = text
    item.self_ref = self_ref
    return item


def _make_ref_item(target: MagicMock) -> MagicMock:
    """Create a mock RefItem that resolves to the given target."""
    ref = MagicMock()
    ref.resolve = MagicMock(return_value=target)
    ref.cref = target.self_ref
    return ref


def _make_table_item(self_ref: str = "#/tables/0") -> MagicMock:
    """Create a mock Docling TableItem."""
    table = MagicMock()
    table.self_ref = self_ref
    table.data = MagicMock()
    table.data.num_rows = 5
    table.data.num_cols = 6
    return table


def _make_group_item(
    label_value: str,
    children: list[MagicMock],
    self_ref: str = "#/groups/0",
) -> MagicMock:
    """Create a mock Docling GroupItem."""
    group = MagicMock()
    group.self_ref = self_ref
    group.label = MagicMock()
    group.label.value = label_value
    group.children = [_make_ref_item(c) for c in children]
    return group


class TestClassify:
    def test_tables_become_table_sections(self) -> None:
        doc = MagicMock()
        doc.tables = [_make_table_item("#/tables/0"), _make_table_item("#/tables/1")]
        doc.groups = []
        doc.texts = []

        sections = classify(doc)

        assert len(sections) == 2
        assert all(s.section_type == SectionType.TABLE for s in sections)
        assert sections[0].table_item is not None

    def test_form_area_with_lab_headers(self) -> None:
        text_items = [
            _make_text_item("TESTS", "#/texts/0"),
            _make_text_item("RESULTS", "#/texts/1"),
            _make_text_item("FLAG", "#/texts/2"),
            _make_text_item("UNITS", "#/texts/3"),
            _make_text_item("REFERENCE INTERVAL", "#/texts/4"),
            _make_text_item("LAB", "#/texts/5"),
            _make_text_item("hCG, Total, Qualitative", "#/texts/6"),
            _make_text_item("<1", "#/texts/7"),
            _make_text_item("", "#/texts/8"),
            _make_text_item("mIU/mL", "#/texts/9"),
            _make_text_item("<5", "#/texts/10"),
            _make_text_item("BN", "#/texts/11"),
        ]
        group = _make_group_item("form_area", text_items)

        doc = MagicMock()
        doc.tables = []
        doc.groups = [group]
        doc.texts = []  # All covered by the group

        sections = classify(doc)

        assert len(sections) == 1
        assert sections[0].section_type == SectionType.FORM
        assert len(sections[0].texts) == 12

    def test_form_area_without_lab_headers_skipped(self) -> None:
        text_items = [
            _make_text_item("Patient Name", "#/texts/0"),
            _make_text_item("John Doe", "#/texts/1"),
        ]
        group = _make_group_item("form_area", text_items)

        doc = MagicMock()
        doc.tables = []
        doc.groups = [group]
        doc.texts = text_items  # Not covered, should be UNSTRUCTURED

        sections = classify(doc)

        # No FORM section, but there should be UNSTRUCTURED
        form_sections = [s for s in sections if s.section_type == SectionType.FORM]
        assert len(form_sections) == 0

    def test_uncovered_text_becomes_unstructured(self) -> None:
        text_items = [
            _make_text_item("Some narrative text", "#/texts/0"),
            _make_text_item("More findings here", "#/texts/1"),
        ]

        doc = MagicMock()
        doc.tables = []
        doc.groups = []
        doc.texts = text_items

        sections = classify(doc)

        assert len(sections) == 1
        assert sections[0].section_type == SectionType.UNSTRUCTURED
        assert sections[0].texts == ["Some narrative text", "More findings here"]

    def test_mixed_document(self) -> None:
        """Document with table + form area + loose text."""
        table = _make_table_item("#/tables/0")

        form_texts = [
            _make_text_item("TESTS", "#/texts/0"),
            _make_text_item("RESULTS", "#/texts/1"),
            _make_text_item("hCG", "#/texts/2"),
            _make_text_item("<1", "#/texts/3"),
        ]
        group = _make_group_item("form_area", form_texts)

        loose_text = _make_text_item("Notes: call patient", "#/texts/4")

        doc = MagicMock()
        doc.tables = [table]
        doc.groups = [group]
        doc.texts = [loose_text]  # Only the loose text is in doc.texts

        sections = classify(doc)

        types = [s.section_type for s in sections]
        assert SectionType.TABLE in types
        assert SectionType.FORM in types
        assert SectionType.UNSTRUCTURED in types

    def test_empty_document(self) -> None:
        doc = MagicMock()
        doc.tables = []
        doc.groups = []
        doc.texts = []

        sections = classify(doc)
        assert sections == []

    def test_key_value_area_with_lab_headers(self) -> None:
        text_items = [
            _make_text_item("TEST", "#/texts/0"),
            _make_text_item("RESULT", "#/texts/1"),
            _make_text_item("WBC", "#/texts/2"),
            _make_text_item("7.5", "#/texts/3"),
        ]
        group = _make_group_item("key_value_area", text_items)

        doc = MagicMock()
        doc.tables = []
        doc.groups = [group]
        doc.texts = []

        sections = classify(doc)

        assert len(sections) == 1
        assert sections[0].section_type == SectionType.FORM
