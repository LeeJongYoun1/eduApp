"""공식 검정 합격 공고 PDF → batch/data/textbooks_2022.csv (헤더: subject,grade,semester,publisher,title)

사용: python batch/scripts/build_textbook_catalog.py <PDF 폴더>   (pip install pypdf pdfplumber)
PDF 출처(2022 개정, 초등):
  수학·과학 3~4학년군 — 한국과학창의재단 공고 제2024-0098호 (kosac.re.kr, 게시판 386 bbIdx=40455, 붙임1)
  수학·과학 5~6학년군 — 한국과학창의재단 공고 제2025-0118호 (kosac.re.kr, 게시판 386 posts/42428, 붙임1)
  사회·체육·영어·미술·음악·실과 — 한국교육과정평가원 교과용도서 검정 사업단 tbh.kice.re.kr/review-results.do 의
    2024-approval-elementary.pdf, 2024-reapproval-elementary-music.pdf,
    2025-approval-elementary.pdf, 2025-approval-elementary-social-music-english.pdf
폴더에 필요한 파일: 2024-math-science.pdf(수학·과학 3~4), 2025-math-science.pdf(수학·과학 5~6), 위 KICE 4개.
shortcut: 교과서와 지도서 행의 발행사를 합쳐 과목·학년군별 합격 발행사로 본다(표 추출에서 행이 빠져도 보완), 공고가 바뀌면 PDF를 다시 받아 재실행.
"""
import csv, re, sys
from collections import defaultdict
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

STRIP = re.compile(r"\(주\)|㈜|주식회사|\s")
ADDR = re.compile(r"^(서울|경기|인천|부산|대구|광주|대전|울산|세종|충청|충북|충남|전라|전북|전남|경상|경북|경남|강원|제주)")
MARK = re.compile(r"㈜|\(주\)|주식회사")
ONE_BOOK = {"영어", "음악", "미술", "체육", "실과"}  # 학기 구분 없는 한 권짜리: semester=1로 저장
# 재검정 공고(평가원 제2025-109호)의 표는 열이 밀려 자동 추출이 안 되므로 원문에서 확인한 것을 직접 넣는다:
# 음악 3·4학년 미래엔 (검정번호 초30513-P-01, 초30514-S-01)
MANUAL = {("음악", 3): {"미래엔"}}


def norm(p: str) -> str:
    return STRIP.sub("", p)


def kofac(path: Path, band: str) -> list[tuple[str, str]]:
    """한국과학창의재단 공고(텍스트형 PDF): [(도서명, 발행사)]. 검정번호 뒤 첫 주소 줄 앞의 상호를 읽는다."""
    txt = "\n".join(p.extract_text() for p in PdfReader(path).pages)
    pos = [m.start() for m in re.finditer(r"\b\d\d[MS]\d{4}[A-Z]\b", txt)] + [len(txt)]
    out = []
    for p, end in zip(pos, pos[1:]):
        head = txt[max(0, p - 90):p]
        head = head[head.rfind(band) + len(band):] if band in head else head
        title = re.sub(r"\s+", " ", re.sub(r"\s*20\d\d\. *\d+\. *\d+\.\s*$", "", head.strip())).strip()
        lines = txt[p:end].split("\n")
        ai = next((i for i, l in enumerate(lines) if ADDR.match(l.strip())), None)
        if ai is None:
            continue
        j = ai - 1
        while j >= 0 and not MARK.search(lines[j]):
            j -= 1
        if j >= 0:
            toks = " ".join(l.strip() for l in lines[j:ai]).split()
            out.append((title, norm("".join(toks[:-1]) if len(toks) > 1 else toks[0])))
    return out


def kice(path: Path) -> list[tuple[str, str]]:
    """평가원 공고(표 PDF): 열 0=도서명, 2=검정번호(초…), 13=발행사 상호."""
    out = []
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            for tb in pg.extract_tables():
                for r in tb:
                    r = [(c or "").replace("\n", "").strip() for c in r]
                    if len(r) >= 14 and r[2].startswith("초") and not re.search(r"모조지|스티커|아트지", r[13]):
                        out.append((re.sub(r"\s+", "", r[0]), norm(r[13])))
    return out


def build(d: Path) -> list[tuple]:
    rows = []  # (subject, grade, semester, publisher, title)
    for f, grades, band in (("2024-math-science.pdf", (3, 4), "(3~4학년군)"), ("2025-math-science.pdf", (5, 6), "(5~6학년군)")):
        pubs = defaultdict(set)
        for title, pub in kofac(d / f, band):
            m = re.fullmatch(r"(수학|과학) (\d)-(\d)", title)
            if m and int(m.group(2)) in grades:
                pubs[(m.group(1), int(m.group(2)), int(m.group(3)))].add(pub)
        for (subj, g, s), ps in pubs.items():
            rows += [(subj, g, s, p, f"{subj} {g}-{s}") for p in ps]
    kr = [r for f in ("2024-approval-elementary.pdf", "2024-reapproval-elementary-music.pdf",
                      "2025-approval-elementary.pdf", "2025-approval-elementary-social-music-english.pdf")
          for r in kice(d / f)]
    band_pubs = defaultdict(set)  # (과목, 학년군) → 합격 발행사 (교과서+지도서)
    for title, pub in kr:
        m = re.match(r"(사회과부도|사회|체육|영어|미술|음악|실과)(?:지도서?)?\s*(\d)", title)
        if title.startswith("사회과부도"):
            band_pubs[("사회과부도", 5)].add(pub)
        elif m and pub:
            band_pubs[(m.group(1), 3 if int(m.group(2)) <= 4 else 5)].add(pub)
    for k, v in MANUAL.items():
        band_pubs[k] |= v
    for (subj, b), ps in band_pubs.items():
        for p in ps:
            if subj == "사회과부도":
                rows += [(subj, g, 1, p, "사회과부도 5~6") for g in (5, 6)]
            elif subj == "사회":
                rows += [(subj, g, s, p, f"사회 {g}-{s}") for g in (b, b + 1) for s in (1, 2)]
            elif subj in ONE_BOOK:
                gs = (b, b + 1) if not (subj == "실과" and b == 3) else ()
                rows += [(subj, g, 1, p, f"{subj} {g}") for g in gs]
    return sorted(set(rows))


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "data" / "textbooks_2022.csv"
    rows = build(Path(sys.argv[1]))
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["subject", "grade", "semester", "publisher", "title"])
        w.writerows(rows)
    print(len(rows), "rows ->", out)
