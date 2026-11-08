# Recorrência civil

**Estado:** completo

Perfil de datas civis gregorianas de 0001 a 9999. A leitura e a expansão são offline e não alteram a entrada. Referência: RFC 5545 §§3.3.10 e 3.8.5, com as restrições deste perfil; não implica conformidade integral iCalendar.

## Cobertura

**Janela inclusiva:** 2026-01-01 a 2026-12-31.

Expansão completa até 2026-12-31.

**Razão de parada:** nenhuma.

## Série

**DTSTART:** 2026-01-30

**Regra canônica:** `FREQ=MONTHLY;INTERVAL=1;COUNT=6;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1;WKST=MO`

**RDATE:** 2026-04-01

**EXDATE:** 2026-03-31

As datas da série e suas exceções podem revelar informações sensíveis; o relatório não é anônimo.

## Orçamentos

| Métrica | Valor |
| --- | --- |
| maxPeriods | 10000 |
| maxDays | 100000 |
| maxOccurrences | 5000 |

## Estatísticas desta expansão

| Métrica | Valor |
| --- | --- |
| periodsEvaluated | 6 |
| daysExamined | 181 |
| validationDays | 31 |
| ruleOccurrencesConsumed | 6 |
| resultsEmitted | 6 |

validationDays é o custo de sincronização de DTSTART, separado de daysExamined. COUNT é consumido antes de EXDATE e do recorte da janela.

## Datas e origens

| Data | Origens |
| --- | --- |
| 2026-01-30 | dtstart, rrule |
| 2026-02-27 | rrule |
| 2026-04-01 | rdate |
| 2026-04-30 | rrule |
| 2026-05-29 | rrule |
| 2026-06-30 | rrule |
