"""Tests for region grouper -- spatial clustering of Docling elements."""

from unittest.mock import MagicMock

from longview_health.extract.region_grouper import (
    DocumentRegion,
    group_regions,
)


def _make_text_item(text: str, label: str, page_no: int, bbox: tuple[float, float, float, float]):
    """Make a mock Docling text item with provenance."""
    item = MagicMock()
    item.text = text
    item.label = MagicMock()
    item.label.value = label

    prov = MagicMock()
    prov.page_no = page_no
    prov.bbox.l = bbox[0]
    prov.bbox.t = bbox[1]
    prov.bbox.r = bbox[2]
    prov.bbox.b = bbox[3]
    prov.bbox.coord_origin = MagicMock()
    prov.bbox.coord_origin.value = "BOTTOMLEFT"
    item.prov = [prov]

    return item


def _make_table_item(text_grid: list[list[str]], page_no: int, bbox: tuple[float, float, float, float]):
    """Make a mock Docling table item with grid data."""
    table = MagicMock()

    prov = MagicMock()
    prov.page_no = page_no
    prov.bbox.l = bbox[0]
    prov.bbox.t = bbox[1]
    prov.bbox.r = bbox[2]
    prov.bbox.b = bbox[3]
    table.prov = [prov]

    cells = []
    for row_idx, row in enumerate(text_grid):
        for col_idx, cell_text in enumerate(row):
            cell = MagicMock()
            cell.text = cell_text
            cell.start_row_offset_idx = row_idx
            cell.start_col_offset_idx = col_idx
            cells.append(cell)

    data = MagicMock()
    data.num_rows = len(text_grid)
    data.num_cols = len(text_grid[0]) if text_grid else 0
    data.table_cells = cells
    table.data = data

    return table


class TestGroupRegions:
    def test_empty_document(self) -> None:
        doc = MagicMock()
        doc.tables = []
        doc.texts = []

        regions = group_regions(doc)
        assert regions == []

    def test_table_gets_own_region(self) -> None:
        table = _make_table_item(
            [["TESTS", "RESULT"], ["WBC", "7.5"]],
            page_no=1,
            bbox=(50, 700, 500, 400),
        )

        doc = MagicMock()
        doc.tables = [table]
        doc.texts = []

        regions = group_regions(doc)

        assert len(regions) == 1
        assert regions[0].label == "table"
        assert regions[0].table_item is table
        assert "WBC" in regions[0].text
        assert "7.5" in regions[0].text

    def test_text_items_grouped_by_proximity(self) -> None:
        """Text items close together form a single region."""
        doc = MagicMock()
        doc.tables = []
        doc.texts = [
            _make_text_item("Line 1", "text", 1, (50, 700, 400, 690)),
            _make_text_item("Line 2", "text", 1, (50, 685, 400, 675)),
            _make_text_item("Line 3", "text", 1, (50, 670, 400, 660)),
        ]

        regions = group_regions(doc)

        assert len(regions) == 1
        assert "Line 1" in regions[0].text
        assert "Line 2" in regions[0].text
        assert "Line 3" in regions[0].text

    def test_large_y_gap_splits_regions(self) -> None:
        """Text items with a big vertical gap form separate regions."""
        doc = MagicMock()
        doc.tables = []
        doc.texts = [
            _make_text_item("Group A", "text", 1, (50, 700, 400, 690)),
            # 50-unit gap (> 30 threshold)
            _make_text_item("Group B", "text", 1, (50, 600, 400, 590)),
        ]

        regions = group_regions(doc)

        assert len(regions) == 2
        assert "Group A" in regions[0].text
        assert "Group B" in regions[1].text

    def test_section_header_splits_regions(self) -> None:
        """Section headers start a new region."""
        doc = MagicMock()
        doc.tables = []
        doc.texts = [
            _make_text_item("Intro text", "text", 1, (50, 700, 400, 690)),
            _make_text_item("Lab Results", "section_header", 1, (50, 680, 400, 670)),
            _make_text_item("WBC: 7.5", "text", 1, (50, 665, 400, 655)),
        ]

        regions = group_regions(doc)

        assert len(regions) == 2
        assert "Intro text" in regions[0].text
        assert "Lab Results" in regions[1].text
        assert "WBC: 7.5" in regions[1].text

    def test_page_headers_excluded(self) -> None:
        """Page headers and footers are not included in regions."""
        doc = MagicMock()
        doc.tables = []
        doc.texts = [
            _make_text_item("Patient Name", "page_header", 1, (50, 770, 200, 760)),
            _make_text_item("Result content", "text", 1, (50, 700, 400, 690)),
            _make_text_item("Page 1 of 2", "page_footer", 1, (50, 50, 200, 40)),
        ]

        regions = group_regions(doc)

        assert len(regions) == 1
        assert "Result content" in regions[0].text
        assert "Patient Name" not in regions[0].text
        assert "Page 1 of 2" not in regions[0].text

    def test_new_page_starts_new_region(self) -> None:
        """Elements on different pages are in separate regions."""
        doc = MagicMock()
        doc.tables = []
        doc.texts = [
            _make_text_item("Page 1 content", "text", 1, (50, 700, 400, 690)),
            _make_text_item("Page 2 content", "text", 2, (50, 700, 400, 690)),
        ]

        regions = group_regions(doc)

        assert len(regions) == 2
        page_1 = [r for r in regions if r.page_no == 1]
        page_2 = [r for r in regions if r.page_no == 2]
        assert len(page_1) == 1
        assert len(page_2) == 1
        assert "Page 1 content" in page_1[0].text
        assert "Page 2 content" in page_2[0].text

    def test_mixed_tables_and_text(self) -> None:
        """Tables and text elements coexist in correct order."""
        table = _make_table_item(
            [["TESTS", "RESULT"], ["WBC", "7.5"]],
            page_no=1,
            bbox=(50, 700, 500, 500),
        )

        doc = MagicMock()
        doc.tables = [table]
        doc.texts = [
            _make_text_item("Header text", "section_header", 1, (50, 750, 300, 740)),
            _make_text_item("Footer note", "text", 1, (50, 300, 400, 290)),
        ]

        regions = group_regions(doc)

        # Should have table region + text regions
        assert len(regions) >= 2
        table_regions = [r for r in regions if r.label == "table"]
        assert len(table_regions) == 1

    def test_empty_text_items_excluded(self) -> None:
        """Text items with empty text are excluded."""
        doc = MagicMock()
        doc.tables = []
        doc.texts = [
            _make_text_item("", "text", 1, (50, 700, 400, 690)),
            _make_text_item("   ", "text", 1, (50, 680, 400, 670)),
            _make_text_item("Actual content", "text", 1, (50, 660, 400, 650)),
        ]

        regions = group_regions(doc)

        assert len(regions) == 1
        assert "Actual content" in regions[0].text
