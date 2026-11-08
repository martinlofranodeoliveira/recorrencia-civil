"""Install one wheel without runtime dependencies and exercise it outside src."""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def main(argv=None):
    parser = argparse.ArgumentParser(description='Confere um wheel instalado fora da árvore de fontes.')
    parser.add_argument('--wheel', type=Path, required=True)
    args = parser.parse_args(argv)
    wheel = args.wheel.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='civil-installed-') as temporary:
        work = Path(temporary)
        environment = work / 'environment'
        venv.EnvBuilder(with_pip=True).create(environment)
        binaries = environment / ('Scripts' if os.name == 'nt' else 'bin')
        python = binaries / ('python.exe' if os.name == 'nt' else 'python')
        entry = binaries / ('recorrencia-civil.exe' if os.name == 'nt' else 'recorrencia-civil')
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        env['PYTHONNOUSERSITE'] = '1'
        env['PYTHONIOENCODING'] = 'utf-8'
        subprocess.run([str(python), '-I', '-m', 'pip', 'install', '--no-deps',
                        '--disable-pip-version-check', str(wheel)], cwd=work, env=env, check=True)
        document = {'schemaVersion': 1, 'series': {'dtstart': '2026-01-30',
            'rrule': 'FREQ=MONTHLY;COUNT=6;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1',
            'rdates': ['2026-04-01'], 'exdates': ['2026-03-31']},
            'window': {'start': '2026-01-01', 'end': '2026-12-31'}}
        source = work / 'synthetic.json'
        raw = (json.dumps(document, indent=2) + '\n').encode()
        source.write_bytes(raw)
        expected = ['2026-01-30', '2026-02-27', '2026-04-01',
                    '2026-04-30', '2026-05-29', '2026-06-30']

        child = '''import json, pathlib, sys
import recorrencia_civil as civil
report = civil.expand_document(json.loads(pathlib.Path('synthetic.json').read_text(encoding='utf-8')))
assert report['complete'] and len(report['occurrences']) == 6
assert 'dateutil' not in sys.modules and 'tzdata' not in sys.modules
assert pathlib.Path(civil.__file__).is_relative_to(pathlib.Path(sys.prefix))
print(json.dumps({name: render(report) for name, render in (
 ('json', civil.to_json), ('markdown', civil.to_markdown), ('csv', civil.to_csv))}))
'''
        api = subprocess.run([str(python), '-I', '-c', child], cwd=work, env=env,
                             capture_output=True, check=True)
        assert not api.stderr
        reference = {name: text.encode('utf-8') for name, text in json.loads(api.stdout).items()}

        def command(arguments):
            return subprocess.run([str(entry), *arguments], cwd=work, env=env,
                                  capture_output=True)

        # Capture raw bytes: universal newline decoding would hide Windows
        # LF -> CRLF and CRLF -> CRCRLF translation on the stdout path.
        formats = {}
        for name in ('json', 'markdown', 'csv'):
            rendered = command([str(source), '--format', name])
            assert rendered.returncode == 0 and not rendered.stderr
            assert rendered.stdout == reference[name], name + ': stdout bytes differ from installed API'
            formats[name] = rendered.stdout
        for name in ('json', 'markdown'):
            assert formats[name].endswith(b'\n') and b'\r' not in formats[name]
        assert formats['csv'].endswith(b'\r\n')
        assert b'\r' not in formats['csv'].replace(b'\r\n', b'')
        assert b'\n' not in formats['csv'].replace(b'\r\n', b'')

        result = command([str(source)])
        assert result.returncode == 0 and not result.stderr
        assert result.stdout == reference['json']
        report = json.loads(result.stdout)
        assert report['complete'] and report['verifiedThrough'] == '2026-12-31'
        assert [item['date'] for item in report['occurrences']] == expected
        assert all(value.encode('ascii') in formats['markdown'] for value in expected)
        stdout_rows = list(csv.reader(io.StringIO(formats['csv'].decode('utf-8'), newline='')))
        assert stdout_rows[0] == ['data', 'origens']
        assert [row[0] for row in stdout_rows[1:]] == expected
        output = work / 'result.csv'
        exported = command([str(source), '--format', 'csv', '--output', str(output)])
        assert exported.returncode == 0 and not exported.stdout and not exported.stderr
        assert output.read_bytes() == reference['csv']
        rows = list(csv.reader(io.StringIO(output.read_bytes().decode('utf-8'), newline='')))
        assert rows == stdout_rows
        before = output.read_bytes()
        repeated = command([str(source), '--format', 'csv', '--output', str(output)])
        assert repeated.returncode == 3 and output.read_bytes() == before
        partial = command([str(source), '--max-periods', '1'])
        assert partial.returncode == 2
        prefix = json.loads(partial.stdout)
        assert not prefix['complete'] and prefix['verifiedThrough'] == '2026-01-31'
        assert [item['date'] for item in prefix['occurrences']] == expected[:1]
        version = command(['--version'])
        assert version.returncode == 0 and not version.stderr
        assert version.stdout.strip() == b'recorrencia-civil 1.0.0'
        assert source.read_bytes() == raw
        print(json.dumps({'installedDistribution': True, 'outsideSourceTree': True,
                         'runtimeThirdPartyImports': 0, 'formats': 3, 'boundedPrefix': True,
                         'exclusiveOutput': True, 'entryPoint': True,
                         'exactStdoutBytes': True, 'csvStdoutParsed': True}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
