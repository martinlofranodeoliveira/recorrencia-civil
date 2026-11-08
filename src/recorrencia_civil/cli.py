"""Bounded local JSON input and exclusive publication of deterministic reports."""
import argparse
from dataclasses import asdict
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

from . import __version__
from .api import expand_document
from .model import ExpansionLimits, MAX_INPUT_BYTES, RecurrenceError
from .parser import load_document
from .report import to_csv, to_json, to_markdown


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _UsageError('Argumentos inválidos. Use --help para consultar o formato aceito.')

    def _print_message(self, message, file=None):
        if message:
            if file is None or file is sys.stdout:
                _write_stdout(message)
            else:
                _diagnostic(message.rstrip('\n'))


def _parser():
    parser = _Parser(prog='recorrencia-civil', allow_abbrev=False,
                     description='Expande conjuntos de datas civis, offline e com janela e orçamentos explícitos.')
    parser.add_argument('file', metavar='FILE', help='Arquivo JSON regular; use - para ler stdin explicitamente.')
    parser.add_argument('--version', action='version', version='recorrencia-civil ' + __version__)
    parser.add_argument('--format', choices=('json', 'markdown', 'csv'), default='json')
    parser.add_argument('--output', metavar='NEW', help='Arquivo NOVO; o diretório pai já deve existir.')
    for key, value in asdict(ExpansionLimits()).items():
        parser.add_argument('--' + key.replace('_', '-'), type=int, default=value,
                            help='Orçamento de enumeração; zero é permitido (padrão: %(default)s).')
    return parser


def _read_input(source):
    try:
        if source == '-':
            stream = getattr(sys.stdin, 'buffer', sys.stdin)
            raw = stream.read(MAX_INPUT_BYTES + 1)
            if type(raw) is str:
                raw = raw.encode('utf-8')
        else:
            descriptor = os.open(source, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0)
                                 | getattr(os, 'O_CLOEXEC', 0))
            try:
                if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                    raise RecurrenceError('input_type', 'A origem deve ser um arquivo regular; stdin exige - explícito.')
                stream = os.fdopen(descriptor, 'rb')
                descriptor = None
                with stream:
                    raw = stream.read(MAX_INPUT_BYTES + 1)
            finally:
                if descriptor is not None:
                    os.close(descriptor)
        if type(raw) is not bytes:
            raise RecurrenceError('input_read', 'Não foi possível ler a entrada JSON.')
        if len(raw) > MAX_INPUT_BYTES:
            raise RecurrenceError('input_size', 'A entrada JSON excede 65536 bytes.')
        if raw.startswith(b'\xef\xbb\xbf'):
            raise RecurrenceError('input_encoding', 'A entrada JSON deve ser UTF-8 sem BOM.')
        return raw.decode('utf-8')
    except (OSError, ValueError, UnicodeError) as error:
        if isinstance(error, RecurrenceError):
            raise
        raise RecurrenceError('input_read', 'Não foi possível ler uma entrada JSON UTF-8 dentro do limite.') from None


def _publish_new(destination, text):
    # Adapted from the MIT publishers in LOFRANO TECNOLOGIA's EPUB Navigation
    # Audit and SQLite Catalog Report; preserve their notices on redistribution.
    destination = Path(destination)
    temporary = None
    try:
        descriptor, name = tempfile.mkstemp(prefix='.recorrencia-civil-', suffix='.tmp', dir=destination.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, destination)
    except FileExistsError:
        raise RecurrenceError('output_exists', 'O destino já existe. Escolha um arquivo novo; nada foi sobrescrito.') from None
    except (OSError, UnicodeError, ValueError, TypeError):
        raise RecurrenceError('output_write', 'Não foi possível publicar um relatório novo com link exclusivo.') from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _silence_broken_stdout():
    # Prevent interpreter shutdown from retrying a failed buffered flush and
    # replacing the documented error status with Python's exit status 120.
    try:
        descriptor = sys.stdout.fileno()
        sink = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(sink, descriptor)
        finally:
            os.close(sink)
    except (OSError, ValueError, AttributeError):
        pass


def _write_stdout(text=None):
    try:
        if text is not None:
            sys.stdout.write(text)
        sys.stdout.flush()
    except (OSError, UnicodeError, ValueError):
        _silence_broken_stdout()
        raise RecurrenceError('output_write', 'Não foi possível escrever o relatório na saída padrão.') from None


def _diagnostic(message):
    try:
        sys.stderr.write(message + '\n')
        sys.stderr.flush()
    except (OSError, UnicodeError, ValueError):
        pass


_ERROR_MESSAGES = {
    'input_type': 'A origem deve ser arquivo regular; use - para stdin.',
    'input_size': 'A entrada excede o limite de 65536 bytes.',
    'input_encoding': 'A entrada deve usar UTF-8 sem BOM.',
    'input_read': 'Não foi possível ler uma entrada JSON UTF-8 dentro do limite.',
    'output_exists': 'O destino já existe. Escolha um arquivo novo; nada foi sobrescrito.',
    'output_write': 'Não foi possível escrever ou publicar o relatório.',
    'dtstart_mismatch': 'DTSTART deve pertencer aos candidatos selecionados do primeiro período.',
    'invalid_report': 'O resultado não tem a forma documentada do relatório.',
}


def main(argv=None):
    try:
        try:
            args = _parser().parse_args(argv)
        except SystemExit as stop:
            _write_stdout()
            return 0 if stop.code == 0 else 3
        except (TypeError, ValueError):
            raise _UsageError('Argumentos inválidos. Use --help para consultar o formato aceito.') from None
        if (not args.file or '\x00' in args.file
                or (args.output is not None and (not args.output or '\x00' in args.output))):
            raise _UsageError('A origem e o destino devem ser textos não vazios e válidos.')
        try:
            limits = ExpansionLimits(**{key: getattr(args, key) for key in asdict(ExpansionLimits())})
        except RecurrenceError:
            raise _UsageError('Orçamentos inválidos. Consulte os intervalos permitidos na documentação.') from None
        report = expand_document(load_document(_read_input(args.file)), limits=limits)
        text = {'json': to_json, 'markdown': to_markdown, 'csv': to_csv}[args.format](report)
        if args.output is None:
            _write_stdout(text)
        else:
            _publish_new(Path(args.output), text)
        return 0 if report['complete'] else 2
    except _UsageError as error:
        _diagnostic('Erro de uso: ' + str(error))
        return 3
    except RecurrenceError as error:
        code = error.code if type(error.code) is str and re.fullmatch(r'[a-z_]{1,64}', error.code) else 'profile'
        _diagnostic('Erro operacional (' + code + '): ' +
                    _ERROR_MESSAGES.get(code, 'A entrada não atende ao perfil documentado.'))
        return 3
    except (OSError, UnicodeError, ValueError):
        _silence_broken_stdout()
        _diagnostic('Erro operacional (io): Não foi possível ler ou escrever os dados.')
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
