import copy
import json
from pathlib import Path

import httpx

from eduapp_batch.models import School
from eduapp_batch.schools_list import parse_school_info
from eduapp_batch.store import PgStore, RestStore

FIX = json.loads((Path(__file__).parent / "fixtures/neis_school_info.json").read_text())


def test_parse_school_info_maps_fields():
    schools = parse_school_info(FIX)
    assert len(schools) == 5
    assert schools[0] == School(neis_code="7652009", edu_office_code="J10", name="가곡초등학교", sido="경기",
                                sigungu="남양주시", homepage_url="https://gagok-e.goegn.kr")
    assert {s.sido for s in schools} == {"경기"}
    assert schools[2].homepage_url == "https://ganap-e.goedy.kr/ganap-e/main.do"  # 앞 공백 제거


def test_parse_school_info_no_data():
    assert parse_school_info({"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}) == []


def test_parse_school_info_seoul_sigungu_and_blank_homepage():
    d = copy.deepcopy(FIX)
    row = d["schoolInfo"][1]["row"][0]
    row.update(LCTN_SC_NM="서울특별시", ORG_RDNMA="서울특별시 용산구 이촌로 1", HMPG_ADRES="http://")
    s = parse_school_info(d)[0]
    assert (s.sido, s.sigungu, s.homepage_url) == ("서울", "용산구", None)


def test_parse_school_info_skips_other_regions():
    d = copy.deepcopy(FIX)
    d["schoolInfo"][1]["row"][0]["LCTN_SC_NM"] = "부산광역시"
    assert len(parse_school_info(d)) == 4


def test_upsert_schools_keeps_collect_status(db):
    store = PgStore(db)
    s = School("1", "J10", "가초", "경기", "과천시", None)
    assert store.upsert_schools([s]) == 1
    db.execute("update schools set collect_status = 'pending'")
    store.upsert_schools([School("1", "J10", "가초등학교", "경기", "과천시", None)])
    assert db.execute("select name, collect_status::text from schools").fetchall() == [("가초등학교", "pending")]


def test_rest_upsert_schools_on_conflict_neis_code():
    seen = []

    def h(req):
        seen.append(req)
        return httpx.Response(201)
    client = httpx.Client(transport=httpx.MockTransport(h), base_url="https://p.supabase.co")
    store = RestStore("https://p.supabase.co", "sb_secret_x", client=client)
    assert store.upsert_schools([School("1", "J10", "가초", "경기", "과천시", None)]) == 1
    r = seen[0]
    assert r.url.path == "/rest/v1/schools" and r.url.params["on_conflict"] == "neis_code"
    assert "resolution=merge-duplicates" in r.headers["Prefer"]
    assert "collect_status" not in json.loads(r.content)[0]


def test_parse_school_info_skips_blank_code():
    d = copy.deepcopy(FIX)
    d["schoolInfo"][1]["row"][0]["SD_SCHUL_CODE"] = "       "
    assert len(parse_school_info(d)) == 4
