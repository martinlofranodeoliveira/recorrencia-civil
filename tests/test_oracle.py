"""Synthetic differential checks; dateutil is a development dependency only.

Fixtures describe the input independently of the implementation's parser and
candidate generation. The oracle receives constructor arguments, never a
canonical rule or an internal object produced by recorrencia_civil.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
import hashlib
import json
import unittest

import dateutil
from dateutil import rrule as du


ORACLE_VERSION = "4.0.0"
FREQUENCIES = {name: getattr(du, name) for name in
               ("DAILY", "WEEKLY", "MONTHLY", "YEARLY")}
WEEKDAYS = {name: getattr(du, name) for name in
            ("MO", "TU", "WE", "TH", "FR", "SA", "SU")}


@dataclass(frozen=True)
class Fixture:
    name: str
    dtstart: str
    start: str
    end: str
    frequency: str | None = None
    interval: int = 1
    count: int | None = None
    until: str | None = None
    bymonth: tuple[int, ...] = ()
    bymonthday: tuple[int, ...] = ()
    byday: tuple[tuple[str, int | None], ...] = ()
    bysetpos: tuple[int, ...] = ()
    wkst: str = "MO"
    rdates: tuple[str, ...] = ()
    exdates: tuple[str, ...] = ()
    expected_dates: tuple[str, ...] | None = None


def _datetime(value: str) -> datetime:
    """Naive midnight is an oracle adapter, not a timezone interpretation."""
    return datetime.combine(date.fromisoformat(value), datetime.min.time())


def series_input(fixture: Fixture) -> dict:
    """Serialize fixture fields directly, without the production parser."""
    rule = None
    if fixture.frequency is not None:
        parts = ["FREQ=" + fixture.frequency,
                 "INTERVAL=" + str(fixture.interval)]
        if fixture.count is not None:
            parts.append("COUNT=" + str(fixture.count))
        if fixture.until is not None:
            parts.append("UNTIL=" + fixture.until.replace("-", ""))
        for label, values in (("BYMONTH", fixture.bymonth),
                              ("BYMONTHDAY", fixture.bymonthday)):
            if values:
                parts.append(label + "=" + ",".join(map(str, values)))
        if fixture.byday:
            parts.append("BYDAY=" + ",".join(
                ("" if ordinal is None else str(ordinal)) + weekday
                for weekday, ordinal in fixture.byday))
        if fixture.bysetpos:
            parts.append("BYSETPOS=" + ",".join(map(str, fixture.bysetpos)))
        parts.append("WKST=" + fixture.wkst)
        rule = ";".join(parts)
    return {"dtstart": fixture.dtstart, "rrule": rule,
            "rdates": list(fixture.rdates), "exdates": list(fixture.exdates)}


def _oracle_rule(fixture: Fixture):
    if fixture.frequency is None:
        return None
    kwargs = {"freq": FREQUENCIES[fixture.frequency],
              "dtstart": _datetime(fixture.dtstart),
              "interval": fixture.interval,
              "wkst": WEEKDAYS[fixture.wkst], "cache": False}
    if fixture.count is not None:
        kwargs["count"] = fixture.count
    if fixture.until is not None:
        kwargs["until"] = _datetime(fixture.until)
    for key, values in (("bymonth", fixture.bymonth),
                        ("bymonthday", fixture.bymonthday),
                        ("bysetpos", fixture.bysetpos)):
        if values:
            kwargs[key] = values
    if fixture.byday:
        kwargs["byweekday"] = tuple(
            WEEKDAYS[weekday] if ordinal is None else WEEKDAYS[weekday](ordinal)
            for weekday, ordinal in fixture.byday)
    return du.rrule(**kwargs)


def oracle_occurrences(fixture: Fixture) -> list[dict]:
    """Query only the explicit inclusive window, even for unbounded rules."""
    start, end = _datetime(fixture.start), _datetime(fixture.end)
    if not date(2024, 1, 1) <= start.date() <= end.date() <= date(2035, 12, 31):
        raise ValueError("A fixture deve usar a janela sintética documentada.")
    rules = du.rruleset(cache=False)
    rules.rdate(_datetime(fixture.dtstart))
    rule = _oracle_rule(fixture)
    rule_dates = set()
    if rule is not None:
        rule_dates = {value.date().isoformat()
                      for value in rule.between(start, end, inc=True)}
        rules.rrule(rule)
    for value in fixture.rdates:
        rules.rdate(_datetime(value))
    for value in fixture.exdates:
        rules.exdate(_datetime(value))
    explicit_dates = set(fixture.rdates)
    expected = []
    for value in rules.between(start, end, inc=True):
        text = value.date().isoformat()
        sources = []
        if text == fixture.dtstart:
            sources.append("dtstart")
        if text in rule_dates:
            sources.append("rrule")
        if text in explicit_dates:
            sources.append("rdate")
        expected.append({"date": text, "sources": sources})
    return expected


def manual_fixtures() -> tuple[Fixture, ...]:
    """Original examples with calendar dates also checked by hand."""
    return (
        Fixture("month_31_skips", "2026-01-31", "2026-01-01", "2026-12-31",
                "MONTHLY", count=4,
                expected_dates=("2026-01-31", "2026-03-31", "2026-05-31", "2026-07-31")),
        Fixture("leap_default", "2024-02-29", "2024-01-01", "2032-12-31",
                "YEARLY", count=3,
                expected_dates=("2024-02-29", "2028-02-29", "2032-02-29")),
        Fixture("year_monthday_expands", "2026-01-15", "2026-01-01", "2026-12-31",
                "YEARLY", count=4, bymonthday=(15,),
                expected_dates=("2026-01-15", "2026-02-15", "2026-03-15", "2026-04-15")),
        Fixture("ordinal_year", "2024-01-01", "2024-01-01", "2026-12-31",
                "YEARLY", count=3, byday=(("MO", 1),),
                expected_dates=("2024-01-01", "2025-01-06", "2026-01-05")),
        Fixture("ordinal_months_in_year", "2024-01-01", "2024-01-01", "2025-12-31",
                "YEARLY", count=4, bymonth=(1, 2), byday=(("MO", 1),),
                expected_dates=("2024-01-01", "2024-02-05", "2025-01-06", "2025-02-03")),
        Fixture("setpos_complete_first_month", "2026-01-15", "2026-01-15", "2026-03-31",
                "MONTHLY", count=3, bymonthday=(1, 15), bysetpos=(2,),
                expected_dates=("2026-01-15", "2026-02-15", "2026-03-15")),
        Fixture("setpos_complete_first_year", "2026-02-28", "2026-02-28", "2028-12-31",
                "YEARLY", count=3, bymonth=(1, 2), bymonthday=(-1,), bysetpos=(2,),
                expected_dates=("2026-02-28", "2027-02-28", "2028-02-29")),
        Fixture("setpos_before_until_cut", "2026-01-30", "2026-01-01", "2026-03-31",
                "MONTHLY", until="2026-02-15",
                byday=tuple((day, None) for day in ("MO", "TU", "WE", "TH", "FR")),
                bysetpos=(-1,), expected_dates=("2026-01-30",)),
        Fixture("weekday_intersection", "2026-02-13", "2026-01-01", "2026-12-31",
                "MONTHLY", count=3, bymonthday=(13,), byday=(("FR", None),),
                expected_dates=("2026-02-13", "2026-03-13", "2026-11-13")),
        Fixture("week_monday", "2026-01-06", "2026-01-01", "2026-03-01",
                "WEEKLY", interval=2, count=6, byday=(("TU", None), ("SU", None)),
                expected_dates=("2026-01-06", "2026-01-11", "2026-01-20", "2026-01-25", "2026-02-03", "2026-02-08")),
        Fixture("week_sunday", "2026-01-06", "2026-01-01", "2026-03-01",
                "WEEKLY", interval=2, count=6, byday=(("TU", None), ("SU", None)), wkst="SU",
                expected_dates=("2026-01-06", "2026-01-18", "2026-01-20", "2026-02-01", "2026-02-03", "2026-02-15")),
        Fixture("union_exclusion_count", "2026-01-01", "2025-12-30", "2026-01-10",
                "DAILY", count=3,
                rdates=("2025-12-31", "2026-01-03", "2026-01-10", "2026-01-10"),
                exdates=("2026-01-01", "2026-01-03"),
                expected_dates=("2025-12-31", "2026-01-02", "2026-01-10")),
        Fixture("until_inclusive_and_rdate", "2026-01-01", "2026-01-01", "2026-01-10",
                "DAILY", until="2026-01-03", rdates=("2026-01-03", "2026-01-10"),
                expected_dates=("2026-01-01", "2026-01-02", "2026-01-03", "2026-01-10")),
        Fixture("count_before_window", "2026-01-01", "2026-01-03", "2026-01-10",
                "DAILY", count=3, exdates=("2026-01-02",),
                expected_dates=("2026-01-03",)),
        Fixture("explicit_only", "2026-01-10", "2026-01-01", "2026-01-31",
                rdates=("2026-01-01", "2026-01-10", "2026-01-20", "2026-01-20"),
                exdates=("2026-01-20",), expected_dates=("2026-01-01", "2026-01-10")),
        Fixture("unbounded_window", "2026-01-30", "2026-02-01", "2026-04-30",
                "MONTHLY", byday=tuple((day, None) for day in ("MO", "TU", "WE", "TH", "FR")),
                bysetpos=(-1,), expected_dates=("2026-02-27", "2026-03-31", "2026-04-30")),
        Fixture("year_plain_weekday", "2024-01-01", "2024-01-01", "2024-02-01",
                "YEARLY", count=4, byday=(("MO", None),),
                expected_dates=("2024-01-01", "2024-01-08", "2024-01-15", "2024-01-22")),
    )


def generated_fixtures() -> tuple[Fixture, ...]:
    """A fixed Cartesian matrix, with matching starts selected by the oracle.

    The finite probe ends in 2034. Selecting a later matching start preserves
    interval phase and lets every generated case satisfy the profile's strict
    DTSTART requirement. Empty probe rules are omitted, not called valid cases.
    """
    weekdays = tuple((day, None) for day in ("MO", "TU", "WE", "TH", "FR"))
    templates = (
        ("DAILY", {}),
        ("DAILY", {"bymonth": (1, 2, 12)}),
        ("DAILY", {"bymonthday": (1, 15, -1)}),
        ("DAILY", {"byday": (("MO", None), ("FR", None))}),
        ("DAILY", {"bymonth": (2, 3), "bymonthday": (1, 28, -1),
                   "byday": (("MO", None), ("WE", None), ("FR", None)), "bysetpos": (1, -1)}),
        ("WEEKLY", {}),
        ("WEEKLY", {"byday": (("TU", None), ("SU", None))}),
        ("WEEKLY", {"byday": (("TU", None), ("SU", None)), "wkst": "SU"}),
        ("WEEKLY", {"bymonth": (2, 3), "byday": (("MO", None), ("WE", None), ("SU", None)),
                    "bysetpos": (1, -1)}),
        ("WEEKLY", {"byday": (("TH", None),), "wkst": "WE", "bysetpos": (-1,)}),
        ("MONTHLY", {}),
        ("MONTHLY", {"bymonth": (1, 2, 6, 12)}),
        ("MONTHLY", {"bymonthday": (1, 15, -1)}),
        ("MONTHLY", {"byday": (("MO", None), ("FR", None))}),
        ("MONTHLY", {"byday": (("FR", 1), ("MO", -1))}),
        ("MONTHLY", {"bymonthday": (1, 15, 28, -1), "byday": (("MO", None), ("FR", 2))}),
        ("MONTHLY", {"byday": weekdays, "bysetpos": (-1,)}),
        ("MONTHLY", {"bymonthday": (1, 15), "bysetpos": (2,)}),
        ("MONTHLY", {"bymonthday": (-1, -2, -31)}),
        ("MONTHLY", {"bymonth": (2,), "bymonthday": (29,)}),
        ("YEARLY", {}),
        ("YEARLY", {"bymonth": (1, 2, 12)}),
        ("YEARLY", {"bymonthday": (15,)}),
        ("YEARLY", {"byday": (("MO", None), ("FR", None))}),
        ("YEARLY", {"byday": (("MO", 1), ("FR", -1))}),
        ("YEARLY", {"bymonth": (1, 2), "byday": (("MO", 1), ("FR", -1))}),
        ("YEARLY", {"bymonth": (1, 2), "bymonthday": (-1,), "bysetpos": (2,)}),
        ("YEARLY", {"bymonthday": (1, 15, -1), "byday": (("MO", None), ("FR", None))}),
        ("YEARLY", {"bymonth": (2,), "bymonthday": (29,)}),
        ("YEARLY", {"bymonth": (1, 6, 12), "bymonthday": (1,), "byday": (("MO", 1),)}),
        ("YEARLY", {"byday": (("MO", None), ("TU", None)), "bysetpos": (1, 60, -1)}),
        ("YEARLY", {"bymonth": (1, 2, 12), "byday": (("MO", None), ("FR", None)),
                    "bysetpos": (-1, 1, 15)}),
    )
    fixtures = []
    for template_index, (frequency, fields) in enumerate(templates):
        for interval in (1, 2, 3):
            for seed in ("2024-01-01", "2025-03-17", "2026-10-15"):
                probe = Fixture("probe", seed, seed, "2034-12-31", frequency,
                                interval=interval, until="2034-12-31", **fields)
                first = next(iter(_oracle_rule(probe)), None)
                if first is None:
                    continue
                index = len(fixtures)
                anchor = first.date()
                offset = (0, 1, 45, 370)[index % 4]
                window_start = anchor + timedelta(days=offset)
                window_end = min(window_start + timedelta(days=740), date(2035, 12, 31))
                if window_start > window_end:
                    continue
                explicit = (anchor - timedelta(days=7), anchor + timedelta(days=2), window_end)
                fixture = replace(
                    probe, name=f"generated_{index:03d}_{frequency.lower()}",
                    dtstart=anchor.isoformat(), start=window_start.isoformat(), end=window_end.isoformat(),
                    count=None if index % 2 else (1, 2, 8, 20)[template_index % 4],
                    until=window_end.isoformat() if index % 2 else None,
                    rdates=tuple(value.isoformat() for value in explicit) + (anchor.isoformat(),),
                    exdates=(anchor.isoformat(),) if index % 3 == 0 else (explicit[1].isoformat(),),
                )
                # The oracle itself must confirm this is a synchronized fixture.
                if next(iter(_oracle_rule(fixture)), None) != _datetime(fixture.dtstart):
                    raise AssertionError("A matriz gerou DTSTART incompatível.")
                fixtures.append(fixture)
    return tuple(fixtures)


def all_fixtures() -> tuple[Fixture, ...]:
    return manual_fixtures() + generated_fixtures()


def check_fixture(fixture: Fixture) -> list[dict]:
    from recorrencia_civil import expand

    series = series_input(fixture)
    original = deepcopy(series)
    report = expand(series, fixture.start, fixture.end)
    if not report["complete"] or report["verifiedThrough"] != fixture.end:
        raise AssertionError("O caso de oráculo não teve cobertura completa.")
    expected = oracle_occurrences(fixture)
    if report["occurrences"] != expected:
        raise AssertionError("As ocorrências ou origens diferem do oráculo.")
    if series != original:
        raise AssertionError("A API alterou a entrada sintética.")
    if fixture.expected_dates is not None:
        if tuple(item["date"] for item in expected) != fixture.expected_dates:
            raise AssertionError("O oráculo diverge da fixture manual.")
    return expected


def check_partition(fixture: Fixture) -> None:
    from recorrencia_civil import expand

    start, end = date.fromisoformat(fixture.start), date.fromisoformat(fixture.end)
    split = start + (end - start) // 2
    if split >= end:
        return
    left = expand(series_input(fixture), fixture.start, split.isoformat())
    right = expand(series_input(fixture), (split + timedelta(days=1)).isoformat(), fixture.end)
    if not left["complete"] or not right["complete"]:
        raise AssertionError("A partição não teve cobertura completa.")
    if left["occurrences"] + right["occurrences"] != oracle_occurrences(fixture):
        raise AssertionError("A janela particionada mudou o conjunto ou as origens.")


def check_weekly_full_period_regression() -> dict:
    """Reproduce a known divergence and check both implementations explicitly.

    dateutil 4.0.0 starts the first WEEKLY candidate set on DTSTART, instead of
    the beginning of its week. With BYSETPOS=2 that drops the selected initial
    Thursday. The profile selects from the complete WKST-aligned week first.
    Upstream issue 1398 and open PR 1575 discuss this behavior; an open proposal
    is not a maintainer-accepted bug decision. This case is reported separately
    from matching differential cases, without changing either implementation.
    """
    from recorrencia_civil import expand

    fixture = Fixture("setpos_complete_first_week", "2026-01-08", "2026-01-08", "2026-02-01",
                      "WEEKLY", count=3, byday=(("MO", None), ("TH", None)), bysetpos=(2,))
    expected = [
        {"date": "2026-01-08", "sources": ["dtstart", "rrule"]},
        {"date": "2026-01-15", "sources": ["rrule"]},
        {"date": "2026-01-22", "sources": ["rrule"]},
    ]
    report = expand(series_input(fixture), fixture.start, fixture.end)
    if not report["complete"] or report["occurrences"] != expected:
        raise AssertionError("A regressão manual de semana completa falhou.")
    if report["stats"]["ruleOccurrencesConsumed"] != 3:
        raise AssertionError("A regressão manual consumiu COUNT incorretamente.")
    oracle_rule_dates = [value.date().isoformat() for value in _oracle_rule(fixture).between(
        _datetime(fixture.start), _datetime(fixture.end), inc=True)]
    oracle_union_dates = [item["date"] for item in oracle_occurrences(fixture)]
    if oracle_rule_dates != ["2026-01-15", "2026-01-22", "2026-01-29"]:
        raise AssertionError("O resultado conhecido da RRULE do oráculo mudou.")
    if oracle_union_dates != ["2026-01-08", "2026-01-15", "2026-01-22", "2026-01-29"]:
        raise AssertionError("O resultado conhecido da união do oráculo mudou.")
    return {
        "id": "weekly_bysetpos_initial_period",
        "input": {"series": series_input(fixture),
                  "window": {"start": fixture.start, "end": fixture.end, "inclusive": True}},
        "engineDates": [item["date"] for item in report["occurrences"]],
        "dateutilRruleDates": oracle_rule_dates,
        "dateutilUnionDates": oracle_union_dates,
        "profilePolicy": "Selecionar BYSETPOS no periodo completo alinhado a WKST antes do corte de DTSTART.",
        "upstream": {"issue": "https://github.com/dateutil/dateutil/issues/1398",
                     "pullRequest": "https://github.com/dateutil/dateutil/pull/1575",
                     "statusObserved": "open_proposal", "statusObservedOn": "2026-11-08"},
        "assessment": "Divergencia conhecida e reproduzida; sem afirmacao de bug aceito upstream.",
    }


def check_corpus() -> dict:
    """Run comparisons and return only reproducible, sanitized metadata."""
    if dateutil.__version__ != ORACLE_VERSION:
        raise RuntimeError("Versão do oráculo diferente da dependência fixada.")
    fixtures = all_fixtures()
    corpus = []
    for fixture in fixtures:
        expected = check_fixture(fixture)
        corpus.append({"case": fixture.name, "series": series_input(fixture),
                       "window": {"start": fixture.start, "end": fixture.end},
                       "occurrences": expected})
    partitions = fixtures[:len(manual_fixtures())] + fixtures[len(manual_fixtures())::5]
    for fixture in partitions:
        check_partition(fixture)
    known_divergences = [check_weekly_full_period_regression()]
    stable_bytes = json.dumps({"matchingCases": corpus, "knownDivergences": known_divergences},
                              sort_keys=True, separators=(",", ":"),
                              ensure_ascii=True).encode("ascii")
    return {"schemaVersion": 1,
            "oracle": {"name": "python-dateutil", "version": dateutil.__version__},
            "cases": {"manual": len(manual_fixtures()),
                      "generated": len(fixtures) - len(manual_fixtures()),
                      "total": len(fixtures), "inclusiveWindowPartitions": len(partitions),
                      "separateProfileRegressions": 1},
            "occurrencesCompared": sum(len(item["occurrences"]) for item in corpus),
            "knownDivergences": known_divergences,
            "corpusSha256": hashlib.sha256(stable_bytes).hexdigest()}


class OracleTests(unittest.TestCase):
    def test_oracle_version(self):
        self.assertEqual(dateutil.__version__, ORACLE_VERSION)

    def test_manual_cases(self):
        for fixture in manual_fixtures():
            with self.subTest(case=fixture.name):
                check_fixture(fixture)

    def test_generated_matrix(self):
        fixtures = generated_fixtures()
        self.assertGreaterEqual(len(fixtures), 250)
        for fixture in fixtures:
            with self.subTest(case=fixture.name):
                check_fixture(fixture)

    def test_inclusive_window_partition(self):
        fixtures = manual_fixtures() + generated_fixtures()[::5]
        for fixture in fixtures:
            with self.subTest(case=fixture.name):
                check_partition(fixture)

    def test_weekly_setpos_complete_initial_period(self):
        check_weekly_full_period_regression()

    def test_budget_reports_only_an_oracle_prefix(self):
        from recorrencia_civil import ExpansionLimits, expand

        for fixture in manual_fixtures():
            if fixture.frequency is None:
                continue
            for periods in (0, 1, 2):
                with self.subTest(case=fixture.name, periods=periods):
                    report = expand(series_input(fixture), fixture.start, fixture.end,
                                    limits=ExpansionLimits(max_periods=periods,
                                                           max_days=1000,
                                                           max_occurrences=5000))
                    verified = report["verifiedThrough"]
                    expected = [item for item in oracle_occurrences(fixture)
                                if verified is not None and item["date"] <= verified]
                    self.assertEqual(report["occurrences"], expected)
                    if report["complete"]:
                        self.assertEqual(verified, fixture.end)

    def test_result_limit_is_a_union_prefix(self):
        from recorrencia_civil import ExpansionLimits, expand

        for fixture in manual_fixtures():
            expected = oracle_occurrences(fixture)
            for cap in (0, 1, 3):
                with self.subTest(case=fixture.name, cap=cap):
                    report = expand(series_input(fixture), fixture.start, fixture.end,
                                    limits=ExpansionLimits(max_occurrences=cap))
                    self.assertEqual(report["occurrences"], expected[:cap])
                    self.assertEqual(report["complete"], len(expected) <= cap)
                    if len(expected) > cap:
                        self.assertEqual(report["stopReason"], "result_limit")


if __name__ == "__main__":
    unittest.main()
