from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Institution:
    key: str
    name: str
    sido: str
    sigungu: str | None
    homepage_url: str


@dataclass(frozen=True)
class Program:
    source_id: str
    title: str
    url: str
    description: str | None = None
    grade_min: int | None = None
    grade_max: int | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    apply_starts_at: datetime | None = None
    apply_ends_at: datetime | None = None
    fee: str | None = None
