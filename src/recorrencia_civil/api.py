"""Public convenience API, with explicit date windows and budgets."""
from .engine import expand_series
from .model import ExpansionLimits, RecurrenceError
from .parser import parse_date, parse_document, parse_series


def _limits(value):
    if type(value) is not ExpansionLimits:
        raise RecurrenceError('invalid_limits', 'Forneça uma instância de ExpansionLimits.')
    return ExpansionLimits(value.max_periods, value.max_days, value.max_occurrences)


def expand(series, window_start, window_end, *, limits=ExpansionLimits()):
    budget = _limits(limits)
    parsed = parse_series(series)
    start, end = parse_date(window_start), parse_date(window_end)
    if start > end:
        raise RecurrenceError('invalid_window', 'O início da janela deve ser igual ou anterior ao fim.')
    return expand_series(parsed, start, end, budget)


def expand_document(document, *, limits=ExpansionLimits()):
    budget = _limits(limits)
    series, start, end = parse_document(document)
    return expand_series(series, start, end, budget)
