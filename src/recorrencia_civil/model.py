"""Immutable internal values and explicit expansion budgets."""
from dataclasses import dataclass
from datetime import date

MAX_INPUT_BYTES = 65_536
MAX_RULE_CHARS = 1024
MAX_EXPLICIT_DATES = 1000
WEEKDAYS = ('MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU')


class RecurrenceError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ExpansionLimits:
    max_periods: int = 10_000
    max_days: int = 100_000
    max_occurrences: int = 5000

    def __post_init__(self):
        for value, maximum in ((self.max_periods, 100_000), (self.max_days, 1_000_000),
                               (self.max_occurrences, 100_000)):
            if type(value) is not int or not 0 <= value <= maximum:
                raise RecurrenceError('invalid_limits', 'Os orçamentos devem ser inteiros dentro dos limites documentados.')


@dataclass(frozen=True)
class DaySpec:
    weekday: int
    ordinal: int | None = None


@dataclass(frozen=True)
class Rule:
    frequency: str
    interval: int
    count: int | None
    until: date | None
    bymonth: tuple[int, ...]
    bymonthday: tuple[int, ...]
    byday: tuple[DaySpec, ...]
    bysetpos: tuple[int, ...]
    week_start: int
    canonical: str


@dataclass(frozen=True)
class Series:
    dtstart: date
    rule: Rule | None
    rdates: tuple[date, ...]
    exdates: tuple[date, ...]
