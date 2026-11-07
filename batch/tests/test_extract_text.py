import io
import zipfile
from pathlib import Path

from pypdf import PdfWriter

from eduapp_batch.extract_text import extract_text

FIX = Path(__file__).parent / "fixtures"


def test_pdf_text():
    assert "천재교육" in extract_text("sample.pdf", (FIX / "sample.pdf").read_bytes())


def test_hwpx_text():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "Contents/section0.xml",
            '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
            'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
            "<hp:p><hp:run><hp:t>과학 4학년</hp:t></hp:run></hp:p>"
            "<hp:p><hp:run><hp:t>천재교육</hp:t></hp:run></hp:p></hs:sec>",
        )
    text = extract_text("A.HWPX", buf.getvalue())
    assert "과학 4학년" in text and "천재교육" in text


def test_hwp_text():
    assert "교과" in extract_text("sample.hwp", (FIX / "sample.hwp").read_bytes())


def test_image_only_pdf_gives_empty_text():
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    assert extract_text("scan.pdf", buf.getvalue()).strip() == ""


def test_unknown_extension_and_corrupt_bytes_give_empty():
    assert extract_text("a.zip", b"x") == ""
    assert extract_text("a.pdf", b"not a pdf") == ""
    assert extract_text("a.hwp", b"not an hwp") == ""
    assert extract_text("a.hwpx", b"not a zip") == ""
