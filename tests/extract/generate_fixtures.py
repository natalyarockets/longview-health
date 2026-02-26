"""Generate test PDF fixtures for parser tests.

Run this script to create test PDFs in tests/fixtures/.
Uses pdfplumber's underlying library (pdfminer) and reportlab-free approach.
"""

from pathlib import Path


def create_simple_lab_pdf(output_path: Path) -> None:
    """Create a minimal PDF with lab-report-like text content."""
    # Minimal valid PDF with text content
    # This creates a bare-bones PDF without needing reportlab
    text_content = (
        "Patient: Jane Doe\n"
        "Date: 2024-03-15\n"
        "Lab Report - Complete Blood Count\n\n"
        "Test            Result    Unit      Reference Range\n"
        "WBC             7.5       K/uL      4.5-11.0\n"
        "RBC             4.8       M/uL      4.0-5.5\n"
        "Hemoglobin      14.2      g/dL      12.0-16.0\n"
        "Hematocrit      42.1      %         36.0-46.0\n"
        "Platelets       250       K/uL      150-400\n"
    )

    # Build a minimal PDF manually
    objects = []

    # Object 1: Catalog
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

    # Object 2: Pages
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")

    # Object 3: Page
    objects.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R "
        b"/MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    )

    # Object 4: Content stream
    lines = text_content.split("\n")
    stream_parts = ["BT", "/F1 10 Tf", "72 720 Td", "14 TL"]
    for line in lines:
        # Escape special PDF characters
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream_parts.append(f"({escaped}) '")
    stream_parts.append("ET")
    stream = "\n".join(stream_parts).encode()
    objects.append(
        f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode()
        + stream
        + b"\nendstream\nendobj\n"
    )

    # Object 5: Font
    objects.append(
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 "
        b"/BaseFont /Courier >>\nendobj\n"
    )

    # Build the PDF
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(b"%PDF-1.4\n")

        offsets = []
        for obj in objects:
            offsets.append(f.tell())
            f.write(obj)

        xref_offset = f.tell()
        f.write(b"xref\n")
        f.write(f"0 {len(objects) + 1}\n".encode())
        f.write(b"0000000000 65535 f \n")
        for offset in offsets:
            f.write(f"{offset:010d} 00000 n \n".encode())

        f.write(b"trailer\n")
        f.write(f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode())
        f.write(b"startxref\n")
        f.write(f"{xref_offset}\n".encode())
        f.write(b"%%EOF\n")


if __name__ == "__main__":
    fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"
    create_simple_lab_pdf(fixtures_dir / "simple_lab_report.pdf")
    print(f"Created: {fixtures_dir / 'simple_lab_report.pdf'}")
