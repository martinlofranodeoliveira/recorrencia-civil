"""Public presentations, bounded CLI input and exclusive report publication."""
import copy
import csv
import errno
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from recorrencia_civil import ExpansionLimits, RecurrenceError, expand_document, to_csv, to_json, to_markdown
from recorrencia_civil import cli


PROJECT = Path(__file__).resolve().parents[1]


def document():
    return {'schemaVersion': 1,
            'series': {'dtstart': '2026-01-01', 'rrule': 'FREQ=DAILY;COUNT=3',
                       'rdates': ['2026-01-04'], 'exdates': ['2026-01-02']},
            'window': {'start': '2026-01-01', 'end': '2026-01-05'}}


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.report = expand_document(document())

    def test_json_order_indentation_newline_and_no_mutation(self):
        before = copy.deepcopy(self.report)
        text = to_json(self.report)
        self.assertEqual(json.loads(text), self.report)
        self.assertTrue(text.startswith('{\n  "schemaVersion": 1,\n  "status": "complete",\n'))
        self.assertTrue(text.endswith('\n'))
        self.assertNotIn('\r', text)
        self.assertEqual(text, to_json(self.report))
        self.assertEqual(list(json.loads(text)), ['schemaVersion', 'status', 'complete', 'stopReason',
                                                 'window', 'verifiedThrough', 'series', 'limits',
                                                 'stats', 'occurrences'])
        for render in (to_json, to_markdown, to_csv):
            self.assertEqual(render(self.report), render(self.report))
        self.assertEqual(self.report, before)
        # Stable order also applies when callers reorder ordinary dictionary keys.
        reordered = dict(reversed(list(self.report.items())))
        self.assertEqual(to_json(reordered), text)

    def test_markdown_explains_profile_rule_prefix_and_exception_privacy(self):
        text = to_markdown(self.report)
        for expected in ('# Recorrência civil', '**Estado:** completo', 'Janela inclusiva',
                         'FREQ=DAILY;INTERVAL=1;COUNT=3;WKST=MO', '2026-01-05',
                         '2026-01-02', 'não é anônimo', 'offline', 'não alteram a entrada',
                         'conformidade integral iCalendar', 'validationDays', 'daysExamined',
                         '| Data | Origens |'):
            self.assertIn(expected, text)
        partial = expand_document(document(), limits=ExpansionLimits(max_periods=0))
        self.assertFalse(partial['complete'])
        text = to_markdown(partial)
        self.assertIn('**Estado:** incompleto', text)
        self.assertIn('orçamento de períodos esgotado', text)
        self.assertIn('Nenhum dia da janela foi completamente verificado', text)
        self.assertIn('não comprova um conjunto vazio', text)
        partial = expand_document(document(), limits=ExpansionLimits(max_occurrences=1))
        self.assertIn('Prefixo verificado até', to_markdown(partial))
        self.assertIn('limite de resultados atingido', to_markdown(partial))

    def test_csv_quotes_every_cell_uses_crlf_and_effective_origin_order(self):
        text = to_csv(self.report)
        self.assertEqual(text, '"data","origens"\r\n'
                              '"2026-01-01","dtstart,rrule"\r\n'
                              '"2026-01-03","rrule"\r\n'
                              '"2026-01-04","rdate"\r\n')
        self.assertEqual(list(csv.reader(io.StringIO(text))), [
            ['data', 'origens'], ['2026-01-01', 'dtstart,rrule'],
            ['2026-01-03', 'rrule'], ['2026-01-04', 'rdate']])
        self.assertNotIn('\n', text.replace('\r\n', ''))
        self.assertEqual(to_csv(expand_document(document(), limits=ExpansionLimits(max_occurrences=0))),
                         '"data","origens"\r\n')

    def test_rule_default_expansion_can_make_canonical_rule_longer_than_input_limit(self):
        weekdays = ('MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU')
        tokens = list(weekdays)
        for ordinal in range(1, 54):
            for weekday in weekdays:
                candidate = str(ordinal) + weekday
                if len('FREQ=YEARLY;COUNT=1;BYDAY=' + ','.join(tokens + [candidate])) <= 1024:
                    tokens.append(candidate)
        source = document()
        source['series']['rrule'] = 'FREQ=YEARLY;COUNT=1;BYDAY=' + ','.join(tokens)
        report = expand_document(source)
        self.assertLessEqual(len(source['series']['rrule']), 1024)
        self.assertGreater(len(report['series']['rrule']), 1024)
        self.assertLessEqual(len(report['series']['rrule']), 1043)
        self.assertEqual(json.loads(to_json(report)), report)
        self.assertIn(report['series']['rrule'], to_markdown(report))
        self.assertTrue(to_csv(report).startswith('"data","origens"\r\n'))

    def test_arbitrary_or_malformed_reports_raise_only_sanitized_profile_errors(self):
        malformed = [None, False, [], {'private': 'PRIVATE_VALUE'}]
        for field, replacement in [('schemaVersion', True), ('status', 'PRIVATE_VALUE'),
                                   ('complete', 1), ('stopReason', 'PRIVATE_VALUE'),
                                   ('window', []), ('verifiedThrough', 'PRIVATE_VALUE'),
                                   ('series', {}), ('limits', {}), ('stats', {}),
                                   ('occurrences', 'PRIVATE_VALUE')]:
            bad = copy.deepcopy(self.report); bad[field] = replacement; malformed.append(bad)
        for path, replacement in [
            (('series', 'dtstart'), '<img src=x>PRIVATE_VALUE'),
            (('series', 'rrule'), 'PRIVATE_VALUE'),
            (('series', 'rdates'), ['2026-01-04', '2026-01-04']),
            (('window', 'start'), '2026-02-30'),
            (('limits', 'maxDays'), True),
            (('stats', 'resultsEmitted'), 0),
        ]:
            bad = copy.deepcopy(self.report); bad[path[0]][path[1]] = replacement; malformed.append(bad)
        for field, replacement in [('date', '=PRIVATE_VALUE'), ('sources', ['=PRIVATE_VALUE']),
                                   ('sources', ['rrule', 'dtstart']), ('sources', ['rrule', 'rrule'])]:
            bad = copy.deepcopy(self.report); bad['occurrences'][0][field] = replacement; malformed.append(bad)
        class DictSubclass(dict):
            pass
        malformed.append(DictSubclass(self.report))
        for bad in malformed:
            for render in (to_json, to_markdown, to_csv):
                with self.subTest(render=render.__name__, field=type(bad).__name__):
                    with self.assertRaises(RecurrenceError) as caught:
                        render(bad)
                    self.assertEqual(caught.exception.code, 'invalid_report')
                    self.assertNotIn('PRIVATE_VALUE', str(caught.exception))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / 'PRIVATE_SOURCE_DOCUMENT.json'
        self.raw = json.dumps(document()).encode('utf-8')
        self.source.write_bytes(self.raw)

    def tearDown(self):
        self.temporary.cleanup()

    def environment(self):
        environment = os.environ.copy()
        environment['PYTHONPATH'] = str(PROJECT / 'src')
        environment['PYTHONIOENCODING'] = 'utf-8'
        return environment

    def run_cli(self, *arguments, input=None):
        return subprocess.run([sys.executable, '-m', 'recorrencia_civil', *map(str, arguments)],
                              cwd=self.root, env=self.environment(), input=input,
                              capture_output=True, timeout=15)

    def assert_private_error(self, result):
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(result.stdout, b'')
        for private in (b'PRIVATE_', str(self.root).encode(), b'Traceback', b'Exception ignored'):
            self.assertNotIn(private, result.stderr)

    def assert_no_temporary(self):
        self.assertEqual(list(self.root.glob('.recorrencia-civil-*.tmp')), [])

    def test_complete_partial_and_all_formats_preserve_source(self):
        for format, render in [('json', to_json), ('markdown', to_markdown), ('csv', to_csv)]:
            for arguments, limits, status in [([], ExpansionLimits(), 0),
                                             (['--max-periods', '0'], ExpansionLimits(max_periods=0), 2),
                                             (['--max-days', '0'], ExpansionLimits(max_days=0), 2),
                                             (['--max-occurrences', '0'], ExpansionLimits(max_occurrences=0), 2)]:
                with self.subTest(format=format, arguments=arguments):
                    result = self.run_cli(self.source, '--format', format, *arguments)
                    self.assertEqual(result.returncode, status, result.stderr)
                    self.assertEqual(result.stderr, b'')
                    self.assertEqual(result.stdout, render(expand_document(document(), limits=limits)).encode())
                    self.assertNotIn(str(self.root).encode(), result.stdout)
                    self.assertNotIn(b'PRIVATE_SOURCE_DOCUMENT', result.stdout)
                    self.assertEqual(self.source.read_bytes(), self.raw)

    def test_stdin_is_explicit_and_has_same_deterministic_output(self):
        result = self.run_cli('-', input=self.raw)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, to_json(expand_document(document())).encode())
        self.assert_private_error(self.run_cli(input=self.raw))

    def test_help_version_and_sanitized_argument_failures(self):
        for option in ('--help', '--version'):
            result = self.run_cli(option)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout)
            self.assertEqual(result.stderr, b'')
        for arguments in ([], [self.source, '--format', 'PRIVATE_FORMAT'],
                          [self.source, '--max-periods', '-1'],
                          [self.source, '--max-days', '1000001'],
                          [self.source, '--max-occurrences', '100001'],
                          [self.source, '--max-periods', 'PRIVATE_INTEGER'],
                          [self.source, '--max-days', 'true'],
                          [self.source, '--max-occurrences', '1.5'],
                          [self.source, '--max-p', '1'],
                          [self.source, '--PRIVATE_UNKNOWN']):
            with self.subTest(arguments=arguments):
                self.assert_private_error(self.run_cli(*arguments))

    def test_invalid_json_encoding_profile_and_byte_limit_are_private(self):
        for raw in (b'PRIVATE_INVALID_JSON', b'\xef\xbb\xbf' + self.raw,
                    b'\xffPRIVATE_INVALID_UTF8', b'{"schemaVersion":NaN}',
                    b'{"schemaVersion":1,"schemaVersion":1}',
                    self.raw + b' PRIVATE_TRAILING', b' ' * 65537,
                    self.raw.replace(b'2026-01-01', b'PRIVATE_INVALID_DATE')):
            with self.subTest(size=len(raw)):
                self.source.write_bytes(raw)
                self.assert_private_error(self.run_cli(self.source))
                self.assertEqual(self.source.read_bytes(), raw)
                self.assert_private_error(self.run_cli('-', input=raw))
        at_limit = self.raw + b' ' * (65536 - len(self.raw))
        result = self.run_cli('-', input=at_limit)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_private_error(self.run_cli('-', input=at_limit + b' '))

    def test_missing_directory_and_fifo_input_fail_without_waiting(self):
        self.assert_private_error(self.run_cli(self.root / 'PRIVATE_MISSING.json'))
        self.assert_private_error(self.run_cli(self.root))
        if hasattr(os, 'mkfifo'):
            fifo = self.root / 'PRIVATE_FIFO'; os.mkfifo(fifo)
            self.assert_private_error(self.run_cli(fifo))

    def test_bounded_reader_requests_only_limit_plus_one_and_checks_fstat(self):
        class ObservedInput(io.BytesIO):
            requested = []
            def read(self, size=-1):
                self.requested.append(size)
                return super().read(size)
        stream = ObservedInput(self.raw)
        with patch.object(cli.sys, 'stdin', io.TextIOWrapper(stream, encoding='utf-8')):
            self.assertEqual(cli._read_input('-'), self.raw.decode())
        self.assertEqual(stream.requested, [65537])
        with patch.object(cli.os, 'fstat', wraps=os.fstat) as inspected:
            self.assertEqual(cli._read_input(str(self.source)), self.raw.decode())
        self.assertEqual(inspected.call_count, 1)

    def test_empty_nul_nontext_arguments_and_closed_stdin_are_sanitized(self):
        for arguments in ([''], ['\x00PRIVATE_SOURCE'], [str(self.source), '--output', ''],
                          [str(self.source), '--output', '\x00PRIVATE_DESTINATION'], [True]):
            output, diagnostic = io.StringIO(), io.StringIO()
            with patch.object(cli.sys, 'stdout', output), patch.object(cli.sys, 'stderr', diagnostic):
                result = cli.main(arguments)
            self.assertEqual(result, 3)
            self.assertEqual(output.getvalue(), '')
            self.assertNotIn('PRIVATE_', diagnostic.getvalue())
        stream = io.TextIOWrapper(io.BytesIO()); stream.close()
        output, diagnostic = io.StringIO(), io.StringIO()
        with patch.object(cli.sys, 'stdin', stream), patch.object(cli.sys, 'stdout', output), patch.object(cli.sys, 'stderr', diagnostic):
            self.assertEqual(cli.main(['-']), 3)
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('Traceback', diagnostic.getvalue())

    def test_new_file_publication_and_existing_input_destination_are_preserved(self):
        for suffix, arguments, status in [('complete', [], 0), ('partial', ['--max-periods', '0'], 2)]:
            destination = self.root / (suffix + '.json')
            result = self.run_cli(self.source, '--output', destination, *arguments)
            self.assertEqual(result.returncode, status, result.stderr)
            self.assertEqual(result.stdout, b'')
            before = destination.read_bytes()
            self.assertEqual(json.loads(before)['complete'], status == 0)
            self.assert_private_error(self.run_cli(self.source, '--output', destination))
            self.assertEqual(destination.read_bytes(), before)
        self.assert_private_error(self.run_cli(self.source, '--output', self.source))
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assert_no_temporary()

    def test_publisher_syncs_complete_bytes_before_link_and_preserves_csv_crlf(self):
        destination = self.root / 'output.csv'; events = []
        original_fsync, original_link = os.fsync, os.link
        text = to_csv(expand_document(document()))
        def sync(descriptor):
            events.append('fsync'); original_fsync(descriptor)
        def link(source, target):
            events.append('link')
            self.assertEqual(Path(source).parent, destination.parent)
            self.assertEqual(Path(source).read_bytes(), text.encode())
            original_link(source, target)
        with patch.object(cli.os, 'fsync', side_effect=sync), patch.object(cli.os, 'link', side_effect=link):
            cli._publish_new(destination, text)
        self.assertEqual(events, ['fsync', 'link'])
        self.assertEqual(destination.read_bytes(), text.encode())
        self.assert_no_temporary()

    def test_destination_created_in_link_race_is_never_removed_or_overwritten(self):
        destination = self.root / 'race.json'; original_link = os.link
        def race(source, target):
            Path(target).write_bytes(b'PRIVATE_OTHER_WRITER')
            original_link(source, target)
        with patch.object(cli.os, 'link', side_effect=race):
            with self.assertRaises(RecurrenceError) as caught:
                cli._publish_new(destination, 'NEW\n')
        self.assertEqual(caught.exception.code, 'output_exists')
        self.assertEqual(destination.read_bytes(), b'PRIVATE_OTHER_WRITER')
        self.assert_no_temporary()

    def test_sync_link_encoding_and_parent_failures_leave_no_partial_file(self):
        for operation in ('fsync', 'link'):
            destination = self.root / (operation + '.json')
            with patch.object(cli.os, operation, side_effect=OSError(errno.EIO, 'PRIVATE_BACKEND')) as call:
                with self.assertRaises(RecurrenceError) as caught:
                    cli._publish_new(destination, 'NEW\n')
            self.assertEqual(caught.exception.code, 'output_write')
            self.assertNotIn('PRIVATE_BACKEND', str(caught.exception))
            self.assertEqual(call.call_count, 1)
            self.assertFalse(destination.exists())
            self.assert_no_temporary()
        for destination, text in [(self.root / 'missing' / 'out.json', 'NEW\n'),
                                  (self.root / 'surrogate.json', '\ud800'),
                                  (self.root / 'PRIVATE_NUL\x00.json', 'NEW\n')]:
            with self.assertRaises(RecurrenceError) as caught:
                cli._publish_new(destination, text)
            self.assertEqual(caught.exception.code, 'output_write')
            self.assertNotIn('PRIVATE_', str(caught.exception))
            self.assert_no_temporary()

    def test_closed_stdout_pipe_returns_three_without_shutdown_traceback(self):
        reader, writer = os.pipe(); os.close(reader)
        try:
            result = subprocess.run([sys.executable, '-m', 'recorrencia_civil', str(self.source)],
                                    cwd=self.root, env=self.environment(), stdout=writer,
                                    stderr=subprocess.PIPE, timeout=15)
        finally:
            os.close(writer)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn(b'output_write', result.stderr)
        for private in (b'PRIVATE_', b'Traceback', b'Exception ignored', str(self.root).encode()):
            self.assertNotIn(private, result.stderr)

    def test_stdout_write_flush_and_stderr_failures_do_not_escape(self):
        class BrokenWrite(io.StringIO):
            def write(self, value):
                raise OSError('PRIVATE_STDOUT_BACKEND')
        class BrokenFlush(io.StringIO):
            def flush(self):
                raise OSError('PRIVATE_STDOUT_BACKEND')
        for stream in (BrokenWrite(), BrokenFlush()):
            diagnostic = io.StringIO()
            with patch.object(cli.sys, 'stdout', stream), patch.object(cli.sys, 'stderr', diagnostic):
                self.assertEqual(cli.main([str(self.source)]), 3)
            self.assertIn('output_write', diagnostic.getvalue())
            self.assertNotIn('PRIVATE_', diagnostic.getvalue())
        with patch.object(cli.sys, 'stderr', BrokenWrite()):
            self.assertEqual(cli.main(['--PRIVATE_UNKNOWN']), 3)


if __name__ == '__main__':
    unittest.main()
