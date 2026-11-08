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

        def command(arguments):
            return subprocess.run([str(entry), *arguments], cwd=work, env=env,
                                  encoding='utf-8', capture_output=True)

        result = command([str(source)])
        assert result.returncode == 0 and not result.stderr
        report = json.loads(result.stdout)
        assert report['complete'] and report['verifiedThrough'] == '2026-12-31'
        assert [item['date'] for item in report['occurrences']] == expected
        markdown = command([str(source), '--format', 'markdown'])
        assert markdown.returncode == 0 and all(value in markdown.stdout for value in expected)
        output = work / 'result.csv'
        exported = command([str(source), '--format', 'csv', '--output', str(output)])
        assert exported.returncode == 0
        rows = list(csv.reader(io.StringIO(output.read_bytes().decode('utf-8'), newline='')))
        assert rows[0] == ['data', 'origens'] and [row[0] for row in rows[1:]] == expected
        before = output.read_bytes()
        repeated = command([str(source), '--format', 'csv', '--output', str(output)])
        assert repeated.returncode == 3 and output.read_bytes() == before
        partial = command([str(source), '--max-periods', '1'])
        assert partial.returncode == 2
        prefix = json.loads(partial.stdout)
        assert not prefix['complete'] and prefix['verifiedThrough'] == '2026-01-31'
        assert [item['date'] for item in prefix['occurrences']] == expected[:1]
        assert command(['--version']).stdout.strip() == 'recorrencia-civil 1.0.0'
        child = '''import json, pathlib, sys
import recorrencia_civil as civil
report = civil.expand_document(json.loads(pathlib.Path('synthetic.json').read_text()))
assert report['complete'] and len(report['occurrences']) == 6
assert 'dateutil' not in sys.modules and 'tzdata' not in sys.modules
assert pathlib.Path(civil.__file__).is_relative_to(pathlib.Path(sys.prefix))
print(json.dumps({'installedDistribution': True, 'outsideSourceTree': True,
 'runtimeThirdPartyImports': 0, 'formats': 3, 'boundedPrefix': True,
 'exclusiveOutput': True, 'entryPoint': True}))
'''
        subprocess.run([str(python), '-I', '-c', child], cwd=work, env=env, check=True)
        assert source.read_bytes() == raw
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
