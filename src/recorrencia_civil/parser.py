"""Strict small-input parsing; no calendar I/O, clock or implicit timezone."""
from datetime import date
import json
import re

from .model import (DaySpec, MAX_EXPLICIT_DATES, MAX_INPUT_BYTES, MAX_RULE_CHARS,
                    RecurrenceError, Rule, Series, WEEKDAYS)

_PARTS = {'FREQ', 'INTERVAL', 'COUNT', 'UNTIL', 'BYMONTH', 'BYMONTHDAY',
          'BYDAY', 'BYSETPOS', 'WKST'}
_FREQUENCIES = {'DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY'}


def _error(code, message):
    raise RecurrenceError(code, message)


def _object(value, allowed, required):
    if type(value) is not dict or len(value) > len(allowed):
        _error('invalid_shape', 'A estrutura contém campos ou tipos fora do contrato.')
    if any(type(key) is not str for key in value):
        _error('invalid_shape', 'A estrutura contém campos ou tipos fora do contrato.')
    keys = set(value)
    if not keys <= set(allowed) or not set(required) <= keys:
        _error('invalid_shape', 'A estrutura contém campos ausentes ou desconhecidos.')
    return value


def parse_date(value):
    if type(value) is not str or re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value) is None:
        _error('invalid_date', 'Use uma data civil válida no formato YYYY-MM-DD, anos 0001 a 9999.')
    try:
        return date(int(value[:4]), int(value[5:7]), int(value[8:]))
    except ValueError:
        _error('invalid_date', 'Use uma data civil válida no formato YYYY-MM-DD, anos 0001 a 9999.')


def _positive(value, maximum):
    if re.fullmatch(r'[0-9]+', value) is None:
        _error('invalid_rule_value', 'Uma parte numérica da regra está fora do perfil documentado.')
    significant = value.lstrip('0') or '0'
    if len(significant) > len(str(maximum)):
        _error('invalid_rule_value', 'Uma parte numérica da regra está fora do perfil documentado.')
    result = int(significant)
    if not 1 <= result <= maximum:
        _error('invalid_rule_value', 'Uma parte numérica da regra está fora do perfil documentado.')
    return result


def _integers(value, maximum, width, *, signed=False):
    pattern = (r'[+-]?' if signed else '') + r'[0-9]{1,' + str(width) + '}'
    values = value.split(',')
    if any(re.fullmatch(pattern, part) is None for part in values):
        _error('invalid_rule_value', 'Uma lista numérica da regra está fora do perfil documentado.')
    result = tuple(sorted(set(int(part) for part in values)))
    if any(not 1 <= abs(part) <= maximum or (not signed and part < 0) for part in result):
        _error('invalid_rule_value', 'Uma lista numérica da regra está fora do perfil documentado.')
    return result


def _days(value):
    result = set()
    for token in value.split(','):
        match = re.fullmatch(r'([+-]?[0-9]{1,2})?(MO|TU|WE|TH|FR|SA|SU)', token)
        if match is None:
            _error('invalid_rule_value', 'A lista BYDAY deve conter dias da semana e ordinais permitidos.')
        ordinal = int(match.group(1)) if match.group(1) is not None else None
        if ordinal is not None and not 1 <= abs(ordinal) <= 53:
            _error('invalid_rule_value', 'Um ordinal BYDAY está fora do intervalo permitido.')
        result.add(DaySpec(WEEKDAYS.index(match.group(2)), ordinal))
    return tuple(sorted(result, key=lambda item: (item.weekday, item.ordinal is not None, item.ordinal or 0)))


def _rule(value):
    if type(value) is not str or not 1 <= len(value) <= MAX_RULE_CHARS:
        _error('invalid_rule', 'RRULE deve ser uma string de até 1024 caracteres, ou null.')
    if any(ord(character) > 127 or character.isspace() or ord(character) < 32 for character in value):
        _error('invalid_rule', 'RRULE deve conter somente partes ASCII, sem espaços ou linhas ICS.')
    parts = {}
    for token in value.upper().split(';'):
        if token.count('=') != 1:
            _error('invalid_rule', 'Use partes NAME=VALUE separadas por ponto e vírgula.')
        key, content = token.split('=')
        if key not in _PARTS:
            _error('unsupported_rule_part', 'A regra contém uma parte fora do perfil de datas civis.')
        if key in parts:
            _error('duplicate_rule_part', 'Uma parte da regra foi informada mais de uma vez.')
        if not content:
            _error('invalid_rule_value', 'Uma parte da regra está vazia.')
        parts[key] = content
    if 'FREQ' not in parts:
        _error('missing_frequency', 'A regra precisa de uma parte FREQ.')
    frequency = parts['FREQ']
    if frequency not in _FREQUENCIES:
        _error('unsupported_frequency', 'Este perfil aceita DAILY, WEEKLY, MONTHLY e YEARLY.')
    if 'COUNT' in parts and 'UNTIL' in parts:
        _error('invalid_rule_combination', 'COUNT e UNTIL não podem ser usados na mesma regra.')
    interval = _positive(parts.get('INTERVAL', '1'), 9999)
    count = _positive(parts['COUNT'], 1_000_000) if 'COUNT' in parts else None
    until = None
    if 'UNTIL' in parts:
        raw = parts['UNTIL']
        if re.fullmatch(r'[0-9]{8}', raw) is None:
            _error('unsupported_until', 'UNTIL deve ser uma data civil básica YYYYMMDD, sem horário ou fuso.')
        until = parse_date(raw[:4] + '-' + raw[4:6] + '-' + raw[6:])
    bymonth = _integers(parts['BYMONTH'], 12, 2) if 'BYMONTH' in parts else ()
    bymonthday = _integers(parts['BYMONTHDAY'], 31, 2, signed=True) if 'BYMONTHDAY' in parts else ()
    byday = _days(parts['BYDAY']) if 'BYDAY' in parts else ()
    bysetpos = _integers(parts['BYSETPOS'], 366, 3, signed=True) if 'BYSETPOS' in parts else ()
    wkst = parts.get('WKST', 'MO')
    if wkst not in WEEKDAYS:
        _error('invalid_rule_value', 'WKST deve ser um dia da semana sem ordinal.')
    if frequency == 'WEEKLY' and bymonthday:
        _error('invalid_rule_combination', 'BYMONTHDAY não pertence ao perfil WEEKLY.')
    if frequency not in {'MONTHLY', 'YEARLY'} and any(item.ordinal is not None for item in byday):
        _error('invalid_rule_combination', 'BYDAY com ordinal exige MONTHLY ou YEARLY.')
    if bysetpos and not any((bymonth, bymonthday, byday)):
        _error('invalid_rule_combination', 'BYSETPOS exige outra parte BY neste perfil.')
    canonical = ['FREQ=' + frequency, 'INTERVAL=' + str(interval)]
    if count is not None:
        canonical.append('COUNT=' + str(count))
    if until is not None:
        canonical.append('UNTIL=' + until.isoformat().replace('-', ''))
    for name, values in [('BYMONTH', bymonth), ('BYMONTHDAY', bymonthday)]:
        if values:
            canonical.append(name + '=' + ','.join(str(item) for item in values))
    if byday:
        canonical.append('BYDAY=' + ','.join((str(item.ordinal) if item.ordinal is not None else '') + WEEKDAYS[item.weekday] for item in byday))
    if bysetpos:
        canonical.append('BYSETPOS=' + ','.join(str(item) for item in bysetpos))
    canonical.append('WKST=' + wkst)
    return Rule(frequency, interval, count, until, bymonth, bymonthday, byday,
                bysetpos, WEEKDAYS.index(wkst), ';'.join(canonical))


def _dates(value):
    if type(value) is not list or len(value) > MAX_EXPLICIT_DATES:
        _error('explicit_date_limit', 'RDATE e EXDATE devem ser listas de até 1000 datas cada.')
    return tuple(sorted(set(parse_date(item) for item in value)))


def parse_series(value):
    data = _object(value, ('dtstart', 'rrule', 'rdates', 'exdates'), ('dtstart',))
    start = parse_date(data['dtstart'])
    rule = _rule(data['rrule']) if data.get('rrule') is not None else None
    if rule is not None and rule.until is not None and rule.until < start:
        _error('until_before_dtstart', 'Este perfil exige UNTIL igual ou posterior a DTSTART.')
    return Series(start, rule, _dates(data.get('rdates', [])), _dates(data.get('exdates', [])))


def series_dict(series):
    return {'dtstart': series.dtstart.isoformat(), 'rrule': series.rule.canonical if series.rule else None,
            'rdates': [value.isoformat() for value in series.rdates],
            'exdates': [value.isoformat() for value in series.exdates]}


def parse_document(value):
    data = _object(value, ('schemaVersion', 'series', 'window'), ('schemaVersion', 'series', 'window'))
    if type(data['schemaVersion']) is not int or data['schemaVersion'] != 1:
        _error('unsupported_schema', 'schemaVersion deve ser o inteiro 1.')
    window = _object(data['window'], ('start', 'end'), ('start', 'end'))
    start, end = parse_date(window['start']), parse_date(window['end'])
    if start > end:
        _error('invalid_window', 'O início da janela deve ser igual ou anterior ao fim.')
    return parse_series(data['series']), start, end


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _error('duplicate_json_key', 'O JSON contém uma chave repetida.')
        result[key] = value
    return result


def load_document(text):
    if type(text) is not str or len(text) > MAX_INPUT_BYTES:
        _error('input_limit', 'A entrada deve ser JSON UTF-8 de até 65536 bytes.')
    try:
        size = len(text.encode('utf-8'))
    except UnicodeError:
        _error('invalid_encoding', 'A entrada contém Unicode inválido.')
    if size > MAX_INPUT_BYTES:
        _error('input_limit', 'A entrada deve ser JSON UTF-8 de até 65536 bytes.')
    if text.startswith('\ufeff'):
        _error('invalid_encoding', 'O JSON deve ser UTF-8 sem BOM.')
    def constant(_):
        _error('invalid_json', 'O JSON contém um valor não permitido.')
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=constant)
    except RecurrenceError:
        raise
    except (ValueError, RecursionError):
        _error('invalid_json', 'Não foi possível ler um documento JSON completo e válido.')
    if type(value) is not dict:
        _error('invalid_shape', 'O documento JSON deve ser um objeto.')
    return value
