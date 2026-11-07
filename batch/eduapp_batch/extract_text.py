"""첨부 파일(.pdf/.hwpx/.hwp) 바이트를 글자로 바꾼다. 실패하면 빈 글자."""
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import PurePath

import olefile
from pypdf import PdfReader


def _pdf(data: bytes) -> str:
    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)


def _hwpx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = sorted(
            n for n in z.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)
        )
        return "\n".join(
            "".join(
                "".join(e.itertext()) for e in ET.fromstring(z.read(n)).iter() if e.tag.endswith("}t")
            )
            for n in names
        )


def _hwp(data: bytes) -> str:
    # shortcut: PrvText is a truncated preview, upgrade to full body parse when a notice's publisher table falls beyond the preview
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
