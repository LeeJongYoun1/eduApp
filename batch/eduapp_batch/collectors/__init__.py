"""기관별 수집기. 새 기관은 모듈을 추가하고 COLLECTORS에 등록한다."""
from collections.abc import Callable
from datetime import date
from typing import Protocol

from ..models import Institution, Program


class Collector(Protocol):
    institution: Institution

    def collect(self, fetch: Callable[[str], str], today: date) -> list[Program]: ...


COLLECTORS: dict[str, Collector] = {}

from .gwacheon_science import GwacheonScience  # noqa: E402

COLLECTORS["gwacheon_science"] = GwacheonScience()
from .museum_korea import MuseumKorea  # noqa: E402

COLLECTORS["museum_korea"] = MuseumKorea()
from .gg_childrens_museum import GgChildrensMuseum  # noqa: E402

COLLECTORS["gg_childrens_museum"] = GgChildrensMuseum()
from .gg_museum import GgMuseum  # noqa: E402

COLLECTORS["gg_museum"] = GgMuseum()
from .hangeul_museum import HangeulMuseum  # noqa: E402

COLLECTORS["hangeul_museum"] = HangeulMuseum()
from .seoul_childrens_museum import SeoulChildrensMuseum  # noqa: E402

COLLECTORS["seoul_childrens_museum"] = SeoulChildrensMuseum()
from .korea_job_world import KoreaJobWorld  # noqa: E402

COLLECTORS["korea_job_world"] = KoreaJobWorld()
from .seoul_grand_park import SeoulGrandPark  # noqa: E402

COLLECTORS["seoul_grand_park"] = SeoulGrandPark()
