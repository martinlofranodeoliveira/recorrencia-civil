"""Expand civil recurrences using complete, explicitly budgeted periods."""
from bisect import bisect_right
from calendar import monthrange
from datetime import date

from .model import ExpansionLimits, RecurrenceError, Rule, Series


_MAX_DAY = date.max.toordinal()


def _periods(anchor: date, rule: Rule):
    """Yield inclusive ordinal bounds, clipping weeks at the civil domain."""
    if rule.frequency == 'DAILY':
        first = anchor.toordinal()
        while first <= _MAX_DAY:
            yield first, first
            first += rule.interval
    elif rule.frequency == 'WEEKLY':
        first = anchor.toordinal() - (anchor.weekday() - rule.week_start) % 7
        while first <= _MAX_DAY:
            yield max(1, first), min(_MAX_DAY, first + 6)
            first += 7 * rule.interval
    elif rule.frequency == 'MONTHLY':
        month_index = (anchor.year - 1) * 12 + anchor.month - 1
        while month_index < 9999 * 12:
            year, month = divmod(month_index, 12)
            year, month = year + 1, month + 1
            first = date(year, month, 1).toordinal()
            yield first, first + monthrange(year, month)[1] - 1
            month_index += rule.interval
    else:  # YEARLY; Rule values have already been validated by the parser.
        year = anchor.year
        while year <= 9999:
            yield date(year, 1, 1).toordinal(), date(year, 12, 31).toordinal()
            year += rule.interval


def _matches_day(value: date, ordinal: int, rule: Rule) -> bool:
    weekday = value.weekday()
    for spec in rule.byday:
        if weekday != spec.weekday:
            continue
        if spec.ordinal is None:
            return True
        if rule.frequency == 'MONTHLY' or rule.bymonth:
            offset = value.day
            length = monthrange(value.year, value.month)[1]
        else:
            first = date(value.year, 1, 1).toordinal()
            offset = ordinal - first + 1
            length = date(value.year, 12, 31).toordinal() - first + 1
        positive = (offset - 1) // 7 + 1
        negative = -((length - offset) // 7 + 1)
        if spec.ordinal in (positive, negative):
            return True
    return False


def _select(anchor: date, rule: Rule, first: int, last: int) -> list[int]:
    """Apply all selectors to a full period, before any temporal cutoffs."""
    candidates = []
    for ordinal in range(first, last + 1):
        value = date.fromordinal(ordinal)
        if rule.bymonth and value.month not in rule.bymonth:
            continue
        if rule.bymonthday:
            length = monthrange(value.year, value.month)[1]
            if value.day not in rule.bymonthday and value.day - length - 1 not in rule.bymonthday:
                continue
        if rule.byday and not _matches_day(value, ordinal, rule):
            continue
        if rule.frequency == 'WEEKLY' and not rule.byday and value.weekday() != anchor.weekday():
            continue
        if rule.frequency == 'MONTHLY' and not rule.bymonthday and not rule.byday:
            if value.day != anchor.day:
                continue
        if rule.frequency == 'YEARLY' and not rule.bymonthday and not rule.byday:
            if value.day != anchor.day or (not rule.bymonth and value.month != anchor.month):
                continue
        candidates.append(ordinal)
    if rule.bysetpos:
        length = len(candidates)
        return sorted({candidates[position - 1 if position > 0 else position]
                       for position in rule.bysetpos if abs(position) <= length})
    return candidates


def expand_series(series: Series, start: date, end: date,
                  limits: ExpansionLimits) -> dict:
    """Return a deterministic report, including only a proven global prefix."""
    from .parser import series_dict

    if start > end:
        raise RecurrenceError('invalid_window', 'O início da janela deve preceder ou coincidir com o fim.')
    window_first, window_last = start.toordinal(), end.toordinal()
    anchor = series.dtstart.toordinal()
    excluded = {value.toordinal() for value in series.exdates}
    # Bit flags preserve the required source order without mutating Series.
    sources = {}

    def include(ordinal, origin):
        if window_first <= ordinal <= window_last and ordinal not in excluded:
            added = ordinal not in sources
            sources[ordinal] = sources.get(ordinal, 0) | origin
            return added
        return False

    include(anchor, 1)
    for value in series.rdates:
        include(value.toordinal(), 4)
    explicit_dates = sorted(sources)

    periods_evaluated = days_examined = validation_days = consumed = 0
    rule_only_count = 0
    verified = window_last
    stop_reason = None
    rule = series.rule
    if rule is not None:
        periods = iter(_periods(series.dtstart, rule))
        current = next(periods)
        validation_days = current[1] - current[0] + 1
        if anchor not in _select(series.dtstart, rule, *current) or (
                rule.until is not None and series.dtstart > rule.until):
            raise RecurrenceError('dtstart_mismatch', 'DTSTART deve pertencer ao primeiro período selecionado pela regra.')
        until = rule.until.toordinal() if rule.until is not None else _MAX_DAY
        while current is not None:
            first, last = current
            earliest = max(first, anchor)
            if earliest > window_last or earliest > until:
                break
            if periods_evaluated >= limits.max_periods:
                stop_reason = 'period_budget'
                verified = min(window_last, earliest - 1)
                break
            cost = last - first + 1
            if days_examined + cost > limits.max_days:
                stop_reason = 'day_budget'
                verified = min(window_last, earliest - 1)
                break
            periods_evaluated += 1
            days_examined += cost
            exhausted = False
            for ordinal in _select(series.dtstart, rule, first, last):
                if ordinal < anchor:
                    continue
                if ordinal > until or ordinal > window_last:
                    break
                consumed += 1
                rule_only_count += include(ordinal, 2)
                if rule.count is not None and consumed >= rule.count:
                    exhausted = True
                    break
            following = next(periods, None)
            # An exhausted finite rule makes all explicit dates safe immediately.
            if exhausted or last >= min(until, window_last) or following is None:
                verified = window_last
                break
            frontier = min(window_last, max(following[0], anchor) - 1)
            # The witness must already belong to the proven, ordered union.
            if rule_only_count + bisect_right(explicit_dates, frontier) > limits.max_occurrences:
                verified = frontier
                stop_reason = 'result_limit'
                break
            current = following

    safe_dates = sorted(ordinal for ordinal in sources if ordinal <= verified)
    if len(safe_dates) > limits.max_occurrences:
        first_omitted = safe_dates[limits.max_occurrences]
        verified = min(verified, first_omitted - 1)
        safe_dates = safe_dates[:limits.max_occurrences]
        stop_reason = 'result_limit'
    complete = stop_reason is None
    source_names = ((1, 'dtstart'), (2, 'rrule'), (4, 'rdate'))
    return {
        'schemaVersion': 1,
        'status': 'complete' if complete else 'incomplete',
        'complete': complete,
        'stopReason': stop_reason,
        'window': {'start': start.isoformat(), 'end': end.isoformat(), 'inclusive': True},
        'verifiedThrough': date.fromordinal(verified).isoformat() if verified >= window_first else None,
        'series': series_dict(series),
        'limits': {'maxPeriods': limits.max_periods, 'maxDays': limits.max_days,
                   'maxOccurrences': limits.max_occurrences},
        'stats': {'periodsEvaluated': periods_evaluated, 'daysExamined': days_examined,
                  'validationDays': validation_days, 'ruleOccurrencesConsumed': consumed,
                  'resultsEmitted': len(safe_dates)},
        'occurrences': [
            {'date': date.fromordinal(ordinal).isoformat(),
             'sources': [name for bit, name in source_names if sources[ordinal] & bit]}
            for ordinal in safe_dates
        ],
    }
