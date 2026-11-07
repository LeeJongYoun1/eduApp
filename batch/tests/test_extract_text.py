import io
import zipfile
from pathlib import Path

from pypdf import PdfWriter

from eduapp_batch import extract_text as extract_mod
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


def test_hwpx_text_after_inline_child_is_kept():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "Contents/section0.xml",
            '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
            'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
            "<hp:p><hp:run><hp:t>과학<hp:tab/>천재교육</hp:t></hp:run></hp:p></hs:sec>",
        )
    assert "천재교육" in extract_text("A.hwpx", buf.getvalue())


def test_hwp_bad_byte_in_preview_keeps_the_rest(monkeypatch):
    class FakeOle:
        def __init__(self, f): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def openstream(self, name):
            return io.BytesIO("과학 천재교육".encode("utf-16le") + b"\x00\xd8")  # 끝에 짝 없는 서로게이트

    monkeypatch.setattr(extract_mod.olefile, "OleFileIO", FakeOle)
    assert "천재교육" in extract_text("a.hwp", b"x")


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


def test_hwp_full_body_not_truncated():
    text = extract_text("a.hwp", (FIX / "assessment_1_1.hwp").read_bytes())
    assert len(text) > 1500  # 미리보기는 1,023자에서 잘렸다
    assert "[2국01-04]" in text
    assert "위 평가계획은 교육과정에 의해 변경 운영될 수 있습니다" in text


def test_hwp_falls_back_to_preview_when_body_unreadable(monkeypatch):
    def boom(data):
        raise ValueError("encrypted")

    monkeypatch.setattr(extract_mod, "_hwp_body", boom)
    assert "교과" in extract_text("a.hwp", (FIX / "sample.hwp").read_bytes())


def _hwpx(sec_xml: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Contents/section0.xml", (
            '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
            'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">' + sec_xml + "</hs:sec>"))
    return buf.getvalue()


def test_hwpx_paragraphs_on_separate_lines():
    data = _hwpx("<hp:p><hp:run><hp:t>가</hp:t><hp:t>다</hp:t></hp:run></hp:p>"
                 "<hp:p><hp:run><hp:t>나</hp:t></hp:run></hp:p>")
    assert extract_text("a.hwpx", data) == "가다\n나"


def test_hwpx_table_cell_paragraphs_on_separate_lines():
    cell = lambda s: f"<hp:tc><hp:subList><hp:p><hp:run><hp:t>{s}</hp:t></hp:run></hp:p></hp:subList></hp:tc>"
    data = _hwpx(f"<hp:p><hp:run><hp:tbl><hp:tr>{cell('과목')}{cell('국어')}</hp:tr></hp:tbl></hp:run></hp:p>")
    assert extract_text("a.hwpx", data).split("\n") == ["과목", "국어"]


def test_real_hwpx_standard_code_starts_a_line():
    text = extract_text("a.hwpx", (FIX / "assessment_4_1.hwpx").read_bytes())
    assert any(line.startswith("[4국02-04]") for line in text.split("\n"))
