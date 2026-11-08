# Recorrência civil

**Estado:** incompleto

Perfil de datas civis gregorianas de 0001 a 9999. A leitura e a expansão são offline e não alteram a entrada. Referência: RFC 5545 §§3.3.10 e 3.8.5, com as restrições deste perfil; não implica conformidade integral iCalendar.

## Cobertura

**Janela inclusiva:** 2025-12-31 a 2026-01-10.

Prefixo verificado até 2026-01-03. Datas posteriores não estão determinadas.

**Razão de parada:** orçamento de períodos esgotado.

## Série

**DTSTART:** 2026-01-01

**Regra canônica:** `FREQ=DAILY;INTERVAL=1;COUNT=10;WKST=MO`

**RDATE:** 2025-12-31, 2026-01-08

**EXDATE:** 2026-01-02

As datas da série e suas exceções podem revelar informações sensíveis; o relatório não é anônimo.

## Orçamentos

| Métrica | Valor |
| --- | --- |
| maxPeriods | 3 |
| maxDays | 100000 |
| maxOccurrences | 5000 |

## Estatísticas desta expansão

| Métrica | Valor |
| --- | --- |
| periodsEvaluated | 3 |
| daysExamined | 3 |
| validationDays | 1 |
| ruleOccurrencesConsumed | 3 |
| resultsEmitted | 3 |

validationDays é o custo de sincronização de DTSTART, separado de daysExamined. COUNT é consumido antes de EXDATE e do recorte da janela.

## Datas e origens

| Data | Origens |
| --- | --- |
| 2025-12-31 | rdate |
| 2026-01-01 | dtstart, rrule |
| 2026-01-03 | rrule |
