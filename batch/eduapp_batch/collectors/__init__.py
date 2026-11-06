"""기관별 수집기. 새 기관은 모듈을 추가하고 COLLECTORS에 등록한다."""
from datetime import date
from typing import Protocol

from ..models import Institution, Program


class Collector(Protocol):
    institution: Institution
    list_urls: list[str]

    def parse(self, html: str, page_url: str, today: date) -> list[Program]: ...


COLLECTORS: dict[str, Collector] = {}
