"""Deterministic presentations of reports produced by the recurrence engine."""
import csv
from datetime import date
import io
import json
import re

from .model import RecurrenceError
from .parser import parse_series, series_dict


_FIELDS = ('schemaVersion', 'status', 'complete', 'stopReason', 'window',
           'verifiedThrough', 'series', 'limits', 'stats', 'occurrences')
_STATS = ('periodsEvaluated', 'daysExamined', 'validationDays',
          'ruleOccurrencesConsumed', 'resultsEmitted')
_SOURCES = ('dtstart', 'rrule', 'rdate')
_REASONS = {
    'period_budget': 'orçamento de períodos esgotado',
    'day_budget': 'orçamento de dias esgotado',
    'result_limit': 'limite de resultados atingido',
}


def _invalid():
    raise RecurrenceError('invalid_report', 'O relatório deve ter a forma produzida pelo engine deste perfil.')


def _keys(value, fields):
    if (type(value) is not dict or len(value) != len(fields)
            or any(type(key) is not str for key in value)
            or set(value) != set(fields)):
        _invalid()


def _day(value):
    if type(value) is not str or re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value) is None:
        _invalid()
    try:
        date.fromisoformat(value)
    except ValueError:
        _invalid()
    return value


def _integer(value, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        _invalid()
    return value


def _date_list(value):
    if type(value) is not list or len(value) > 1000:
        _invalid()
    result = [_day(item) for item in value]
    if result != sorted(set(result)):
        _invalid()
    return result


def _validated(report):
    """Check the closed report shape without recalculating its recurrence."""
    _keys(report, _FIELDS)
    if type(report['schemaVersion']) is not int or report['schemaVersion'] != 1:
        _invalid()
    complete, status, reason = report['complete'], report['status'], report['stopReason']
    if type(complete) is not bool or type(status) is not str:
        _invalid()
    if complete:
        if status != 'complete' or reason is not None:
            _invalid()
    elif status != 'incomplete' or type(reason) is not str or reason not in _REASONS:
        _invalid()
    window = report['window']
    _keys(window, ('start', 'end', 'inclusive'))
    start, end = _day(window['start']), _day(window['end'])
    if start > end or window['inclusive'] is not True:
        _invalid()
    through = report['verifiedThrough']
    if through is not None and not start <= _day(through) <= end:
        _invalid()
    if complete and through != end:
        _invalid()
    series = report['series']
    _keys(series, ('dtstart', 'rrule', 'rdates', 'exdates'))
    dtstart = _day(series['dtstart'])
    rdates, exdates = _date_list(series['rdates']), _date_list(series['exdates'])
    rdate_set, exdate_set = set(rdates), set(exdates)
    rule = series['rrule']
    # Canonicalization may add the two defaults to a 1024-character input.
    if rule is not None and (type(rule) is not str or len(rule) > 1043):
        _invalid()
    clean_series = {'dtstart': dtstart, 'rrule': rule, 'rdates': rdates, 'exdates': exdates}
    try:
        parse_input = dict(clean_series)
        if rule is not None:
            parse_input['rrule'] = ';'.join(part for part in rule.split(';')
                                           if part not in {'INTERVAL=1', 'WKST=MO'})
        if series_dict(parse_series(parse_input)) != clean_series:
            _invalid()
    except (RecurrenceError, TypeError, ValueError, OverflowError):
        _invalid()
    limits = report['limits']
    _keys(limits, ('maxPeriods', 'maxDays', 'maxOccurrences'))
    clean_limits = {
        'maxPeriods': _integer(limits['maxPeriods'], 100_000),
        'maxDays': _integer(limits['maxDays'], 1_000_000),
        'maxOccurrences': _integer(limits['maxOccurrences'], 100_000),
    }
    stats = report['stats']
    _keys(stats, _STATS)
    clean_stats = {key: _integer(stats[key], maximum) for key, maximum in zip(
        _STATS, (clean_limits['maxPeriods'], clean_limits['maxDays'], 366,
                 1_000_000, clean_limits['maxOccurrences']))}
    occurrences = report['occurrences']
    if (type(occurrences) is not list or len(occurrences) > clean_limits['maxOccurrences']
            or len(occurrences) != clean_stats['resultsEmitted']):
        _invalid()
    clean_occurrences = []
    previous = None
    for item in occurrences:
        _keys(item, ('date', 'sources'))
        day, sources = _day(item['date']), item['sources']
        if (through is None or not start <= day <= through
                or (previous is not None and day <= previous)
                or type(sources) is not list or not 1 <= len(sources) <= 3
                or any(type(source) is not str or source not in _SOURCES for source in sources)
                or sources != [source for source in _SOURCES if source in sources]):
            _invalid()
        if (('dtstart' in sources and day != dtstart)
                or ('rrule' in sources and (rule is None or day < dtstart))
                or ('rdate' in sources and day not in rdate_set) or day in exdate_set):
            _invalid()
        clean_occurrences.append({'date': day, 'sources': list(sources)})
        previous = day
    return {
        'schemaVersion': 1, 'status': status, 'complete': complete, 'stopReason': reason,
        'window': {'start': start, 'end': end, 'inclusive': True},
        'verifiedThrough': through, 'series': clean_series, 'limits': clean_limits,
        'stats': clean_stats, 'occurrences': clean_occurrences,
    }


def to_json(report):
    """Return stable JSON with two-space indentation and a final LF."""
    return json.dumps(_validated(report), ensure_ascii=True, indent=2, allow_nan=False) + '\n'


def _table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join('---' for _ in headers) + ' |'] +
                     ['| ' + ' | '.join(str(value) for value in row) + ' |' for row in rows])


def to_markdown(report):
    """Explain the verified prefix and present dates in the declared civil profile."""
    report = _validated(report)
    window, series = report['window'], report['series']
    complete, through = report['complete'], report['verifiedThrough']
    sections = [
        '# Recorrência civil',
        '**Estado:** ' + ('completo' if complete else 'incompleto'),
        'Perfil de datas civis gregorianas de 0001 a 9999. A leitura e a expansão são '
        'offline e não alteram a entrada. Referência: RFC 5545 §§3.3.10 e 3.8.5, com '
        'as restrições deste perfil; não implica conformidade integral iCalendar.',
        '## Cobertura',
        '**Janela inclusiva:** ' + window['start'] + ' a ' + window['end'] + '.',
        ('Expansão completa até ' + through + '.' if complete else
         ('Prefixo verificado até ' + through + '. Datas posteriores não estão determinadas.'
          if through is not None else
          'Nenhum dia da janela foi completamente verificado. A saída vazia não comprova um conjunto vazio.')),
        '**Razão de parada:** ' + ('nenhuma' if complete else _REASONS[report['stopReason']]) + '.',
        '## Série',
        '**DTSTART:** ' + series['dtstart'],
        '**Regra canônica:** ' + ('`' + series['rrule'] + '`' if series['rrule'] else 'ausente'),
        '**RDATE:** ' + (', '.join(series['rdates']) or 'nenhuma'),
        '**EXDATE:** ' + (', '.join(series['exdates']) or 'nenhuma'),
        'As datas da série e suas exceções podem revelar informações sensíveis; o relatório não é anônimo.',
        '## Orçamentos',
        _table(['Métrica', 'Valor'], report['limits'].items()),
        '## Estatísticas desta expansão',
        _table(['Métrica', 'Valor'], report['stats'].items()),
        'validationDays é o custo de sincronização de DTSTART, separado de daysExamined. '
        'COUNT é consumido antes de EXDATE e do recorte da janela.',
        '## Datas e origens',
        _table(['Data', 'Origens'], ((item['date'], ', '.join(item['sources']))
                                   for item in report['occurrences'])),
    ]
    if not report['occurrences']:
        sections.append('Nenhuma ocorrência no prefixo verificado.' if not complete else
                        'Nenhuma ocorrência na janela completa.')
    return '\n\n'.join(sections) + '\n'


def to_csv(report):
    """Return only validated dates and protocol origins, with quoted CRLF cells."""
    report = _validated(report)
    output = io.StringIO(newline='')
    writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator='\r\n')
    writer.writerow(('data', 'origens'))
    for item in report['occurrences']:
        writer.writerow((item['date'], ','.join(item['sources'])))
    return output.getvalue()
