"""Behavioral checks for civil dates, complete periods, and proven coverage."""
from copy import deepcopy
from datetime import date
import unittest

from recorrencia_civil.engine import expand_series
from recorrencia_civil.model import ExpansionLimits, RecurrenceError
from recorrencia_civil.parser import parse_series


class EngineTests(unittest.TestCase):
    def expand(self, dtstart, rule=None, start=None, end=None, *, rdates=(), exdates=(), limits=None):
        payload = {'dtstart': dtstart, 'rrule': rule, 'rdates': list(rdates), 'exdates': list(exdates)}
        return expand_series(parse_series(payload), date.fromisoformat(start or dtstart),
                             date.fromisoformat(end or dtstart), limits or ExpansionLimits())

    def dates(self, report):
        return [item['date'] for item in report['occurrences']]

    def test_month_end_is_skipped_instead_of_clamped(self):
        report = self.expand('2024-01-31', 'FREQ=MONTHLY;COUNT=4', end='2024-12-31')
        self.assertEqual(self.dates(report), ['2024-01-31', '2024-03-31', '2024-05-31', '2024-07-31'])
        self.assertEqual(report['stats']['ruleOccurrencesConsumed'], 4)
        self.assertTrue(report['complete'])

    def test_leap_day_is_skipped_in_nonleap_years(self):
        report = self.expand('2024-02-29', 'FREQ=YEARLY;COUNT=3', end='2032-12-31')
        self.assertEqual(self.dates(report), ['2024-02-29', '2028-02-29', '2032-02-29'])

    def test_set_positions_use_the_period_before_dtstart_and_window(self):
        report = self.expand('2024-01-10', 'FREQ=MONTHLY;BYMONTHDAY=1,10,20;BYSETPOS=2',
                             start='2024-01-11', end='2024-03-10')
        self.assertEqual(self.dates(report), ['2024-02-10', '2024-03-10'])
        self.assertEqual(report['stats']['ruleOccurrencesConsumed'], 3)

    def test_set_positions_use_the_period_before_until(self):
        report = self.expand('2024-01-10', 'FREQ=MONTHLY;UNTIL=20240209;BYMONTHDAY=1,10,20;BYSETPOS=2',
                             end='2024-03-31')
        self.assertEqual(self.dates(report), ['2024-01-10'])
        self.assertTrue(report['complete'])

    def test_positive_and_negative_positions_deduplicate(self):
        report = self.expand('2024-01-31', 'FREQ=MONTHLY;COUNT=2;BYMONTHDAY=31;BYSETPOS=1,-1',
                             end='2024-04-30')
        self.assertEqual(self.dates(report), ['2024-01-31', '2024-03-31'])
        self.assertEqual(report['stats']['ruleOccurrencesConsumed'], 2)

    def test_yearly_monthday_without_bymonth_expands_all_months(self):
        report = self.expand('2024-01-15', 'FREQ=YEARLY;COUNT=4;BYMONTHDAY=15', end='2024-12-31')
        self.assertEqual(self.dates(report), ['2024-01-15', '2024-02-15', '2024-03-15', '2024-04-15'])

    def test_yearly_ordinal_without_bymonth_is_relative_to_year(self):
        report = self.expand('2024-01-01', 'FREQ=YEARLY;COUNT=4;BYDAY=1MO,-1MO', end='2025-12-31')
        self.assertEqual(self.dates(report), ['2024-01-01', '2024-12-30', '2025-01-06', '2025-12-29'])

    def test_yearly_ordinal_with_bymonth_is_relative_to_each_month(self):
        report = self.expand('2024-01-01', 'FREQ=YEARLY;BYMONTH=1,2;BYDAY=1MO;COUNT=4', end='2025-12-31')
        self.assertEqual(self.dates(report), ['2024-01-01', '2024-02-05', '2025-01-06', '2025-02-03'])

    def test_monthday_and_ordinal_weekday_intersect(self):
        report = self.expand('2024-01-01', 'FREQ=MONTHLY;BYMONTHDAY=1,2,3;BYDAY=1MO;COUNT=3',
                             end='2024-12-31')
        self.assertEqual(self.dates(report), ['2024-01-01', '2024-04-01', '2024-06-03'])

    def test_week_start_changes_interval_buckets(self):
        mo = self.expand('1997-08-05', 'FREQ=WEEKLY;INTERVAL=2;COUNT=4;BYDAY=TU,SU;WKST=MO',
                         end='1997-09-30')
        su = self.expand('1997-08-05', 'FREQ=WEEKLY;INTERVAL=2;COUNT=4;BYDAY=TU,SU;WKST=SU',
                         end='1997-09-30')
        self.assertEqual(self.dates(mo), ['1997-08-05', '1997-08-10', '1997-08-19', '1997-08-24'])
        self.assertEqual(self.dates(su), ['1997-08-05', '1997-08-17', '1997-08-19', '1997-08-31'])

    def test_count_is_global_and_consumes_exclusions(self):
        report = self.expand('2024-01-01', 'FREQ=DAILY;COUNT=3', start='2024-01-03', end='2024-02-01',
                             exdates=['2024-01-01', '2024-01-03'], rdates=['2024-01-20'])
        self.assertEqual(self.dates(report), ['2024-01-20'])
        self.assertEqual(report['stats']['ruleOccurrencesConsumed'], 3)
        self.assertTrue(report['complete'])

    def test_count_does_not_restart_in_a_late_window(self):
        report = self.expand('2024-01-01', 'FREQ=DAILY;COUNT=3', start='2024-01-10', end='2024-01-12')
        self.assertEqual(self.dates(report), [])
        self.assertEqual(report['stats']['ruleOccurrencesConsumed'], 3)
        self.assertTrue(report['complete'])
        self.assertEqual(report['verifiedThrough'], '2024-01-12')

    def test_endpoints_are_inclusive_and_rule_stats_stop_at_window(self):
        report = self.expand('2024-01-01', 'FREQ=DAILY', start='2024-01-02', end='2024-01-03')
        self.assertEqual(self.dates(report), ['2024-01-02', '2024-01-03'])
        self.assertEqual(report['stats']['ruleOccurrencesConsumed'], 3)
        self.assertEqual(report['verifiedThrough'], '2024-01-03')

    def test_explicit_union_exclusion_and_source_order(self):
        report = self.expand('2024-01-02', 'FREQ=DAILY;COUNT=2', start='2024-01-01', end='2024-01-10',
                             rdates=['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-09'],
                             exdates=['2024-01-03'])
        self.assertEqual(report['occurrences'], [
            {'date': '2024-01-01', 'sources': ['rdate']},
            {'date': '2024-01-02', 'sources': ['dtstart', 'rrule', 'rdate']},
            {'date': '2024-01-09', 'sources': ['rdate']},
        ])

    def test_rdate_is_not_cut_off_by_until(self):
        report = self.expand('2024-01-01', 'FREQ=DAILY;UNTIL=20240102', end='2024-01-31',
                             rdates=['2024-01-31'])
        self.assertEqual(self.dates(report), ['2024-01-01', '2024-01-02', '2024-01-31'])

    def test_dtstart_removed_by_exdate_remains_rule_anchor(self):
        report = self.expand('2024-01-01', 'FREQ=DAILY;INTERVAL=2;COUNT=3', end='2024-01-06',
                             exdates=['2024-01-01'])
        self.assertEqual(self.dates(report), ['2024-01-03', '2024-01-05'])
        self.assertEqual(report['stats']['ruleOccurrencesConsumed'], 3)

    def test_mismatch_is_rejected_even_with_no_enumeration_budget(self):
        with self.assertRaises(RecurrenceError) as caught:
            self.expand('2024-01-02', 'FREQ=MONTHLY;BYDAY=MO;BYSETPOS=1', end='2024-02-01',
                        limits=ExpansionLimits(0, 0, 0))
        self.assertEqual(caught.exception.code, 'dtstart_mismatch')

    def test_validation_cost_is_separate_and_period_budget_is_atomic(self):
        report = self.expand('2024-01-31', 'FREQ=MONTHLY', start='2024-01-01', end='2024-03-31',
                             limits=ExpansionLimits(1, 31, 10), rdates=['2024-02-01', '2024-03-31'])
        self.assertEqual(self.dates(report), ['2024-01-31'])
        self.assertEqual(report['verifiedThrough'], '2024-01-31')
        self.assertEqual(report['stopReason'], 'period_budget')
        self.assertEqual(report['stats'], {'periodsEvaluated': 1, 'daysExamined': 31,
                                          'validationDays': 31, 'ruleOccurrencesConsumed': 1,
                                          'resultsEmitted': 1})

    def test_day_budget_does_not_consume_partial_period(self):
        report = self.expand('2024-01-31', 'FREQ=MONTHLY', start='2024-01-01', end='2024-03-31',
                             limits=ExpansionLimits(10, 59, 10))
        self.assertEqual(report['stopReason'], 'day_budget')
        self.assertEqual(report['stats']['daysExamined'], 31)
        self.assertEqual(report['stats']['periodsEvaluated'], 1)
        self.assertEqual(report['verifiedThrough'], '2024-01-31')

    def test_exact_day_and_period_budgets_can_be_complete(self):
        report = self.expand('2024-01-01', 'FREQ=MONTHLY', end='2024-02-29',
                             limits=ExpansionLimits(2, 60, 2))
        self.assertTrue(report['complete'])
        self.assertEqual(report['stats']['daysExamined'], 60)
        self.assertEqual(report['stats']['periodsEvaluated'], 2)
        self.assertEqual(report['stats']['validationDays'], 31)

    def test_zero_budget_empty_prefix_is_incomplete(self):
        report = self.expand('2024-01-01', 'FREQ=DAILY', end='2024-01-10',
                             limits=ExpansionLimits(0, 0, 10), rdates=['2024-01-10'])
        self.assertEqual(self.dates(report), [])
        self.assertFalse(report['complete'])
        self.assertEqual(report['stopReason'], 'period_budget')
        self.assertIsNone(report['verifiedThrough'])
        self.assertEqual(report['stats']['validationDays'], 1)

    def test_rdate_before_budget_frontier_is_emitted_but_later_is_held(self):
        report = self.expand('2024-01-10', 'FREQ=DAILY', start='2024-01-01', end='2024-01-20',
                             rdates=['2024-01-01', '2024-01-09', '2024-01-10', '2024-01-20'],
                             limits=ExpansionLimits(0, 0, 10))
        self.assertEqual(self.dates(report), ['2024-01-01', '2024-01-09'])
        self.assertEqual(report['verifiedThrough'], '2024-01-09')

    def test_interval_gap_is_verified_without_enumerating_skipped_days(self):
        report = self.expand('2024-01-01', 'FREQ=DAILY;INTERVAL=10', end='2024-01-20',
                             limits=ExpansionLimits(1, 1, 10), rdates=['2024-01-10', '2024-01-11'])
        self.assertEqual(self.dates(report), ['2024-01-01', '2024-01-10'])
        self.assertEqual(report['verifiedThrough'], '2024-01-10')
        self.assertEqual(report['stats']['daysExamined'], 1)

    def test_no_rule_knows_all_explicit_dates_even_with_zero_budgets(self):
        report = self.expand('2024-01-02', start='2024-01-01', end='2024-01-31',
                             rdates=['2024-01-01', '2024-01-31'], limits=ExpansionLimits(0, 0, 3))
        self.assertTrue(report['complete'])
        self.assertEqual(self.dates(report), ['2024-01-01', '2024-01-02', '2024-01-31'])
        self.assertEqual(report['stats']['validationDays'], 0)
        self.assertEqual(report['stats']['periodsEvaluated'], 0)

    def test_window_before_dtstart_is_complete_without_enumeration(self):
        report = self.expand('2024-02-01', 'FREQ=YEARLY', start='2024-01-01', end='2024-01-31',
                             rdates=['2024-01-10'], limits=ExpansionLimits(0, 0, 10))
        self.assertTrue(report['complete'])
        self.assertEqual(self.dates(report), ['2024-01-10'])
        self.assertEqual(report['stats']['daysExamined'], 0)
        self.assertEqual(report['stats']['validationDays'], 366)

    def test_result_limit_requires_an_additional_result(self):
        exact = self.expand('2024-01-01', 'FREQ=DAILY;COUNT=2', end='2024-01-31',
                            limits=ExpansionLimits(10, 10, 2))
        self.assertTrue(exact['complete'])
        overflow = self.expand('2024-01-01', 'FREQ=DAILY;COUNT=3', end='2024-01-31',
                               limits=ExpansionLimits(10, 10, 2))
        self.assertFalse(overflow['complete'])
        self.assertEqual(overflow['stopReason'], 'result_limit')
        self.assertEqual(self.dates(overflow), ['2024-01-01', '2024-01-02'])
        self.assertEqual(overflow['verifiedThrough'], '2024-01-02')

    def test_result_cap_without_a_safe_extra_result_preserves_budget_reason(self):
        report = self.expand('2024-01-01', 'FREQ=DAILY', end='2024-01-31',
                             limits=ExpansionLimits(1, 1, 1))
        self.assertEqual(self.dates(report), ['2024-01-01'])
        self.assertEqual(report['stopReason'], 'period_budget')
        self.assertEqual(report['verifiedThrough'], '2024-01-01')

    def test_count_exhaustion_makes_late_rdates_safe_at_exact_budget(self):
        report = self.expand('2024-01-01', 'FREQ=DAILY;COUNT=1', end='2024-12-31',
                             rdates=['2024-12-31'], limits=ExpansionLimits(1, 1, 2))
        self.assertTrue(report['complete'])
        self.assertEqual(self.dates(report), ['2024-01-01', '2024-12-31'])
        self.assertEqual(report['verifiedThrough'], '2024-12-31')

    def test_zero_result_limit_empty_complete_and_nonempty_incomplete(self):
        empty = self.expand('2024-01-01', end='2024-01-31', exdates=['2024-01-01'],
                            limits=ExpansionLimits(0, 0, 0))
        self.assertTrue(empty['complete'])
        self.assertEqual(empty['verifiedThrough'], '2024-01-31')
        nonempty = self.expand('2024-01-10', start='2024-01-01', end='2024-01-31',
                               limits=ExpansionLimits(0, 0, 0))
        self.assertFalse(nonempty['complete'])
        self.assertEqual(nonempty['stopReason'], 'result_limit')
        self.assertEqual(nonempty['verifiedThrough'], '2024-01-09')
        self.assertEqual(self.dates(nonempty), [])

    def test_result_limit_witness_overrides_a_budget_stop(self):
        report = self.expand('2024-01-10', 'FREQ=DAILY', start='2024-01-01', end='2024-01-31',
                             rdates=['2024-01-02', '2024-01-05'], limits=ExpansionLimits(0, 0, 1))
        self.assertEqual(report['stopReason'], 'result_limit')
        self.assertEqual(self.dates(report), ['2024-01-02'])
        self.assertEqual(report['verifiedThrough'], '2024-01-04')

    def test_year_one_week_clips_before_domain_without_underflow(self):
        report = self.expand('0001-01-01', 'FREQ=WEEKLY;WKST=SU;COUNT=2', end='0001-01-15')
        self.assertEqual(self.dates(report), ['0001-01-01', '0001-01-08'])
        self.assertEqual(report['stats']['validationDays'], 6)
        self.assertEqual(report['stats']['daysExamined'], 13)

    def test_year_9999_does_not_construct_year_10000(self):
        for frequency in ('DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY'):
            with self.subTest(frequency=frequency):
                report = self.expand('9999-12-31', f'FREQ={frequency}', end='9999-12-31')
                self.assertEqual(self.dates(report), ['9999-12-31'])
                self.assertTrue(report['complete'])
                self.assertEqual(report['verifiedThrough'], '9999-12-31')

    def test_input_is_immutable_and_report_is_detached(self):
        payload = {'dtstart': '2024-01-01', 'rrule': 'FREQ=DAILY;COUNT=2',
                   'rdates': ['2024-01-03', '2024-01-01'], 'exdates': []}
        original = deepcopy(payload)
        series = parse_series(payload)
        report = expand_series(series, date(2024, 1, 1), date(2024, 1, 31), ExpansionLimits())
        self.assertEqual(payload, original)
        baseline = deepcopy(report)
        report['series']['rdates'].append('2024-01-31')
        report['occurrences'][0]['sources'].clear()
        self.assertEqual(expand_series(series, date(2024, 1, 1), date(2024, 1, 31), ExpansionLimits()), baseline)
        self.assertEqual(payload, original)


if __name__ == '__main__':
    unittest.main()
