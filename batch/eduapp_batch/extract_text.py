"""첨부 파일(.pdf/.hwpx/.hwp) 바이트를 글자로 바꾼다. 실패하면 빈 글자."""
import io
import re
import struct
import zipfile
import zlib
import xml.etree.ElementTree as ET
from pathlib import PurePath

import olefile
from pypdf import PdfReader


def _pdf(data: bytes) -> str:
    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)


def _hwpx_lines(el, out: list[str]) -> None:
    """문단(p)마다 한 줄. 표 칸 안의 문단은 바깥 문단 안에 들어 있으므로 따로 한 줄씩 낸다."""
    own: list[str] = []

    def walk(e) -> None:
        for c in e:
            if c.tag.endswith("}p"):
                _hwpx_lines(c, out)
            elif c.tag.endswith("}t"):
                own.append("".join(c.itertext()))
            else:
                walk(c)

    walk(el)
    if "".join(own).strip():
        out.append("".join(own))


def _hwpx(data: bytes) -> str:
    lines: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = sorted(
            (n for n in z.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)),
            key=lambda n: int(re.search(r"\d+", n).group()),
        )
        for n in names:
            _hwpx_lines(ET.fromstring(z.read(n)), lines)
    return "\n".join(lines)


def _hwp_body(data: bytes) -> str:
    """BodyText 전체(문단 레코드 태그 67)를 읽는다. 압축·암호화 등으로 못 읽으면 예외."""
    with olefile.OleFileIO(io.BytesIO(data)) as ole:
        compressed = bool(ole.openstream("FileHeader").read()[36] & 1)
        sections = sorted(
            (s for s in ole.listdir() if s[0] == "BodyText"),
            key=lambda s: int(re.sub(r"\D", "", s[1]) or 0),
        )
        out: list[str] = []
        for name in sections:
            raw = ole.openstream(name).read()
            raw = zlib.decompress(raw, -15) if compressed else raw
            i = 0
            while i < len(raw):
                head = struct.unpack_from("<I", raw, i)[0]
                tag, size = head & 0x3FF, (head >> 20) & 0xFFF
                i += 4
                if size == 0xFFF:
                    size = struct.unpack_from("<I", raw, i)[0]
                    i += 4
                if tag == 67:
                    text = raw[i : i + size].decode("utf-16le", errors="ignore")
                    out.append(re.sub(r"[\x00-\x08\x0b-\x1f]", " ", text).strip())
                i += size
        return "\n".join(x for x in out if x)


def _hwp(data: bytes) -> str:
    try:
        text = _hwp_body(data)
        if text:
            return text
    except Exception:
        pass
    # 배포용 암호화 등으로 본문을 못 읽으면 미리보기(앞부분만)라도 쓴다
    with olefile.OleFileIO(io.BytesIO(data)) as ole:
        return ole.openstream("PrvText").read().decode("utf-16le", errors="ignore")


_READERS = {".pdf": _pdf, ".hwpx": _hwpx, ".hwp": _hwp}


def extract_text(name: str, data: bytes) -> str:
    reader = _READERS.get(PurePath(name).suffix.lower())
    if reader is None:
        return ""
    try:
        return reader(data)
    except Exception:
        return ""
