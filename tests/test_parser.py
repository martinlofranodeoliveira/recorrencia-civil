import copy
from datetime import date, datetime
import json
import unittest

from recorrencia_civil.model import ExpansionLimits, MAX_INPUT_BYTES, RecurrenceError
from recorrencia_civil.parser import load_document, parse_date, parse_document, parse_series, series_dict


class ParserTests(unittest.TestCase):
    def rejects(self, fn, code=None):
        with self.assertRaises(RecurrenceError) as caught:
            fn()
        if code is not None:
            self.assertEqual(caught.exception.code, code)
        self.assertNotIn('PRIVATE_CANARY', str(caught.exception))

    def test_calendar_date_lexing_and_leap_boundaries(self):
        for value in ['0001-01-01', '9999-12-31', '2000-02-29', '2024-02-29']:
            self.assertEqual(parse_date(value).isoformat(), value)
        for value in [None, True, date(2026, 1, 1), datetime(2026, 1, 1), '2026-1-01',
                      '2026-01-1', '2026-02-29', '1900-02-29', '0000-01-01',
                      '10000-01-01', '2026-01-01Z', '２０２６-01-01', '2026-01-01\n']:
            with self.subTest(value=repr(value)):
                self.rejects(lambda: parse_date(value), 'invalid_date')

    def test_minimal_series_defaults_and_explicit_date_deduplication(self):
        self.assertEqual(series_dict(parse_series({'dtstart': '2026-01-01'})),
                         {'dtstart': '2026-01-01', 'rrule': None, 'rdates': [], 'exdates': []})
        value = {'dtstart': '2026-01-01', 'rrule': None,
                 'rdates': ['2026-02-01', '2025-12-01', '2026-02-01'],
                 'exdates': ['2026-01-01', '2026-01-01']}
        previous = copy.deepcopy(value)
        parsed = parse_series(value)
        self.assertEqual(series_dict(parsed)['rdates'], ['2025-12-01', '2026-02-01'])
        self.assertEqual(series_dict(parsed)['exdates'], ['2026-01-01'])
        self.assertEqual(value, previous)
        value['rdates'].clear()
        self.assertEqual(len(parsed.rdates), 2)

    def test_rule_parts_are_order_and_case_independent_with_explicit_defaults(self):
        first = parse_series({'dtstart': '2026-01-31', 'rrule': 'count=0004;freq=monthly'})
        second = parse_series({'dtstart': '2026-01-31', 'rrule': 'FREQ=MONTHLY;WKST=MO;INTERVAL=01;COUNT=4'})
        self.assertEqual(first, second)
        self.assertEqual(first.rule.canonical, 'FREQ=MONTHLY;INTERVAL=1;COUNT=4;WKST=MO')

    def test_signed_lists_and_weekday_union_have_a_stable_canonical_order(self):
        result = parse_series({'dtstart': '2026-01-01', 'rrule':
            'FREQ=YEARLY;BYDAY=1TU,MO,+1MO,-1MO,MO;BYMONTHDAY=+01,-1,1;BYMONTH=12,01,1;BYSETPOS=+001,-1,1'})
        self.assertEqual(result.rule.canonical,
            'FREQ=YEARLY;INTERVAL=1;BYMONTH=1,12;BYMONTHDAY=-1,1;BYDAY=MO,-1MO,1MO,1TU;BYSETPOS=-1,1;WKST=MO')

    def test_until_is_date_only_inclusive_shape_and_profile_ordered(self):
        value = parse_series({'dtstart': '2026-01-01', 'rrule': 'FREQ=DAILY;UNTIL=20260101'})
        self.assertEqual(value.rule.until, date(2026, 1, 1))
        self.rejects(lambda: parse_series({'dtstart': '2026-01-02', 'rrule': 'FREQ=DAILY;UNTIL=20260101'}), 'until_before_dtstart')
        for until in ['2026-01-01', '20260101T000000Z', '20260101T000000', '20260229']:
            self.rejects(lambda: parse_series({'dtstart': '2026-01-01', 'rrule': 'FREQ=DAILY;UNTIL=' + until}))

    def test_invalid_rule_combinations_are_explicit(self):
        for rule in ['FREQ=DAILY;COUNT=1;UNTIL=20260101', 'FREQ=WEEKLY;BYMONTHDAY=1',
                     'FREQ=WEEKLY;BYDAY=1MO', 'FREQ=DAILY;BYDAY=-1MO',
                     'FREQ=MONTHLY;BYSETPOS=-1']:
            self.rejects(lambda: parse_series({'dtstart': '2026-01-01', 'rrule': rule}), 'invalid_rule_combination')

    def test_unsupported_rule_parts_and_frequencies_are_not_ignored(self):
        for part in ['BYHOUR=0', 'BYMINUTE=0', 'BYSECOND=0', 'BYWEEKNO=1',
                     'BYYEARDAY=1', 'BYEASTER=0', 'RSCALE=GREGORIAN', 'PRIVATE_CANARY=1']:
            self.rejects(lambda: parse_series({'dtstart': '2026-01-01', 'rrule': 'FREQ=YEARLY;' + part}), 'unsupported_rule_part')
        for freq in ['HOURLY', 'MINUTELY', 'SECONDLY', 'PRIVATE_CANARY']:
            self.rejects(lambda: parse_series({'dtstart': '2026-01-01', 'rrule': 'FREQ=' + freq}), 'unsupported_frequency')

    def test_part_duplication_and_non_rule_property_lines_are_refused(self):
        self.rejects(lambda: parse_series({'dtstart': '2026-01-01', 'rrule': 'FREQ=DAILY;freq=DAILY'}), 'duplicate_rule_part')
        self.rejects(lambda: parse_series({'dtstart': '2026-01-01', 'rrule': 'COUNT=3'}), 'missing_frequency')
        for rule in ['', None, False, 1, [], {}, 'FREQ=DAILY;', ';FREQ=DAILY',
                     'FREQ =DAILY', 'FREQ=DAILY\n', 'RRULE:FREQ=DAILY',
                     'FREQ=DAILY;COUNT==1', 'FREQ=DAILY;COUNT=', 'FREQ=DAILY;' + 'X' * 1024]:
            if rule is None:
                continue  # null explicitly means no RRULE.
            self.rejects(lambda: parse_series({'dtstart': '2026-01-01', 'rrule': rule}))

    def test_numeric_profile_limits_and_grammar_widths(self):
        for part in ['COUNT=0', 'COUNT=-1', 'COUNT=+1', 'COUNT=1000001', 'INTERVAL=0',
                     'INTERVAL=10000', 'INTERVAL=1.0', 'BYMONTH=0', 'BYMONTH=13',
                     'BYMONTH=+1', 'BYMONTH=001', 'BYMONTHDAY=0', 'BYMONTHDAY=-32',
                     'BYDAY=0MO', 'BYDAY=54MO', 'BYDAY=001MO', 'BYSETPOS=0',
                     'BYSETPOS=367', 'BYSETPOS=0001', 'WKST=1MO', 'BYMONTH=1,,2']:
            rule = 'FREQ=YEARLY;BYDAY=MO;' + part if part.startswith('BYSETPOS=') else 'FREQ=YEARLY;' + part
            self.rejects(lambda: parse_series({'dtstart': '2026-01-01', 'rrule': rule}))
        valid = parse_series({'dtstart': '2026-01-01', 'rrule': 'FREQ=YEARLY;COUNT=1000000;INTERVAL=9999;BYDAY=-53MO,53SU;BYSETPOS=-366,366'})
        self.assertEqual(valid.rule.count, 1_000_000)

    def test_explicit_date_limit_is_before_deduplication(self):
        parse_series({'dtstart': '2026-01-01', 'rdates': ['2026-01-01'] * 1000})
        self.rejects(lambda: parse_series({'dtstart': '2026-01-01', 'rdates': ['2026-01-01'] * 1001}), 'explicit_date_limit')
        for value in [None, (), '2026-01-01', {'2026-01-01': 1}]:
            self.rejects(lambda: parse_series({'dtstart': '2026-01-01', 'exdates': value}), 'explicit_date_limit')

    def test_schema_types_shapes_and_inclusive_window(self):
        doc = {'schemaVersion': 1, 'series': {'dtstart': '2026-01-01'},
               'window': {'start': '2026-01-01', 'end': '2026-01-01'}}
        previous = copy.deepcopy(doc)
        _, start, end = parse_document(doc)
        self.assertEqual(start, end)
        self.assertEqual(doc, previous)
        for version in [True, False, 1.0, '1', 0, 2, None]:
            bad = {**doc, 'schemaVersion': version}
            self.rejects(lambda: parse_document(bad), 'unsupported_schema')
        self.rejects(lambda: parse_document({**doc, 'PRIVATE_CANARY': 1}), 'invalid_shape')
        self.rejects(lambda: parse_document({**doc, 'window': {'start': '2026-01-02', 'end': '2026-01-01'}}), 'invalid_window')
        self.rejects(lambda: parse_document({**doc, 'window': {'start': '2026-01-01', 'end': '2026-01-01', 'inclusive': True}}), 'invalid_shape')

    def test_user_defined_containers_are_not_executed(self):
        class Hostile(dict):
            def get(self, *_):
                raise AssertionError('Container was executed')
        self.rejects(lambda: parse_series(Hostile(dtstart='2026-01-01')), 'invalid_shape')
        for value in [[], None, {'dtstart': '2026-01-01', 1: 'PRIVATE_CANARY'},
                      {'dtstart': '2026-01-01', 'unknown': 'PRIVATE_CANARY'}]:
            self.rejects(lambda: parse_series(value), 'invalid_shape')

    def test_json_duplicate_keys_constants_bom_trailer_and_unicode_are_rejected(self):
        self.rejects(lambda: load_document('{"a":1,"a":2}'), 'duplicate_json_key')
        self.rejects(lambda: load_document('{"a":{"b":1,"b":2}}'), 'duplicate_json_key')
        for text in ['{"a":NaN}', '{"a":Infinity}', '{"a":-Infinity}', '{}{}',
                     '\ufeff{}', '[]', 'null', 'PRIVATE_CANARY', '{"a":"\ud800"}']:
            self.rejects(lambda: load_document(text))
        self.assertEqual(load_document(' {"a": [null, true, 1]}\n'), {'a': [None, True, 1]})

    def test_json_limit_measures_utf8_bytes_not_characters(self):
        text = '{"x":"' + '\u00e9' * ((MAX_INPUT_BYTES - 8) // 2) + '"}'
        self.assertEqual(len(text.encode()), MAX_INPUT_BYTES)
        self.assertEqual(len(load_document(text)['x']), 32764)
        self.rejects(lambda: load_document(text + ' '), 'input_limit')
        self.assertEqual(load_document('{}' + ' ' * (MAX_INPUT_BYTES - 2)), {})
        self.rejects(lambda: load_document(' ' * (MAX_INPUT_BYTES + 1)), 'input_limit')

    def test_budget_types_zero_and_hard_ceilings(self):
        self.assertEqual(ExpansionLimits(0, 0, 0).max_occurrences, 0)
        self.assertEqual(ExpansionLimits(100000, 1000000, 100000).max_days, 1000000)
        for field, maximum in [('max_periods', 100000), ('max_days', 1000000), ('max_occurrences', 100000)]:
            for value in [True, False, -1, 1.0, '1', maximum + 1, None]:
                with self.subTest(field=field, value=value):
                    self.rejects(lambda: ExpansionLimits(**{field: value}), 'invalid_limits')


if __name__ == '__main__':
    unittest.main()
