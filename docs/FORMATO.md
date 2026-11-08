# Entrada, API e relatórios · versão 1

Recorrência Civil expande conjuntos de datas gregorianas entre `0001-01-01` e `9999-12-31`. A operação é local, de leitura, sem relógio implícito, horários, fusos, duração, execução de agenda ou parser ICS. O contrato completo está em [SPEC.md](../SPEC.md). Este perfil referencia RFC 5545 §§3.3.10 e 3.8.5 e as erratas declaradas no contrato; não afirma conformidade integral iCalendar.

## API pública

```python
from recorrencia_civil import (
    ExpansionLimits,
    RecurrenceError,
    expand,
    expand_document,
    to_csv,
    to_json,
    to_markdown,
)

series = {
    "dtstart": "2026-01-31",
    "rrule": "FREQ=MONTHLY;COUNT=4",
    "rdates": ["2026-02-28"],
    "exdates": ["2026-03-31"],
}
report = expand(series, "2026-01-01", "2026-12-31")
assert report["complete"]
assert [item["date"] for item in report["occurrences"]] == [
    "2026-01-31", "2026-02-28", "2026-05-31", "2026-07-31"
]
text = to_json(report)
```

Assinaturas:

```python
expand(series, window_start, window_end, *, limits=ExpansionLimits()) -> dict
expand_document(document, *, limits=ExpansionLimits()) -> dict
to_json(report) -> str
to_markdown(report) -> str
to_csv(report) -> str
```

Os wrappers não alteram seus argumentos nem fazem I/O. Datas são strings ASCII exatas `YYYY-MM-DD`; objetos `date`, `datetime`, subclasses e coerções de tipos ficam fora da entrada pública. `series` deve ser um `dict` comum: `dtstart` é obrigatório e somente `rrule`, `rdates` e `exdates` são opcionais. Os defaults são `null`, `[]` e `[]`. Cada lista explícita aceita até 1000 datas antes da deduplicação. Duplicatas são normalizadas e ordenadas.

A janela inclui as duas pontas e exige início igual ou anterior ao fim. COUNT é contado desde DTSTART, antes de EXDATE e da janela. RDATE não consome COUNT e pode anteceder DTSTART. EXDATE pode remover a própria âncora. Meses sem o dia solicitado são omitidos; uma regra mensal iniciada em 31 de janeiro não é ajustada para o último dia de fevereiro.

`RecurrenceError` herda de `ValueError` e fornece `.code`. Mensagens não repetem valores rejeitados. Códigos incluem `invalid_date`, `invalid_shape`, `invalid_rule`, `invalid_rule_value`, `unsupported_rule_part`, `unsupported_frequency`, `invalid_rule_combination`, `invalid_window`, `invalid_limits` e `dtstart_mismatch`. Este último indica DTSTART ausente dos candidatos selecionados do primeiro período: a API não inventa uma expansão para esse caso.

## Documento JSON

```json
{
  "schemaVersion": 1,
  "series": {
    "dtstart": "2026-01-31",
    "rrule": "FREQ=MONTHLY;COUNT=4",
    "rdates": [],
    "exdates": []
  },
  "window": {
    "start": "2026-01-01",
    "end": "2026-12-31"
  }
}
```

`schemaVersion`, `series` e `window` são chaves exatas e obrigatórias; o objeto `window` exige exatamente `start` e `end`. `schemaVersion` deve ser o inteiro `1`; `true` é recusado. O documento para `expand_document` segue o mesmo contrato de tipos da API.

A CLI lê no máximo 65537 bytes para distinguir o teto de 65536 bytes do excesso. O texto deve ser UTF-8 sem BOM. JSON com chaves repetidas, NaN, Infinity, conteúdo posterior ao documento, sintaxe inválida ou estrutura fora do perfil é recusado. O parser interno `load_document(text)` também aplica o teto UTF-8 e o JSON estrito; a API pública de `dict` aplica limites estruturais antes de percorrer listas extensas.

RRULE aceita até 1024 caracteres de entrada, sem espaços, controles, prefixo `RRULE:` ou linhas ICS. Nomes e valores protocolares não diferenciam caixa. A saída canônica ordena as partes como `FREQ;INTERVAL;COUNT` ou `UNTIL;BYMONTH;BYMONTHDAY;BYDAY;BYSETPOS;WKST`; escreve os defaults `INTERVAL=1` e `WKST=MO`. Esses defaults podem aumentar a saída canônica até 1043 caracteres; os renderizadores aceitam essa saída do engine, mas o teto de 1024 continua valendo ao apresentar uma regra como nova entrada à API. Valores de listas são únicos e ordenados. Frequências, partes e restrições estão em [SPEC.md](../SPEC.md).

## Orçamentos e prefixo verificado

```python
limits = ExpansionLimits(
    max_periods=10_000,
    max_days=100_000,
    max_occurrences=5_000,
)
report = expand_document(document, limits=limits)
```

| Campo Python | Campo do relatório | Default | Teto |
| --- | --- | --- | --- |
| `max_periods` | `maxPeriods` | 10000 | 100000 |
| `max_days` | `maxDays` | 100000 | 1000000 |
| `max_occurrences` | `maxOccurrences` | 5000 | 100000 |

Os valores são inteiros exatos; booleanos são recusados e zero é permitido. O argumento `limits` deve ser uma instância exata de `ExpansionLimits`.

A sincronização de DTSTART examina até um período, com no máximo 366 dias. Seu custo aparece em `validationDays`, separado do orçamento `max_days`. Na enumeração, cada período é atômico: seus dias válidos do domínio são reservados antes da análise, sem consumir parcialmente um mês ou calcular BYSETPOS sobre um fragmento.

Quando um orçamento interrompe a expansão, o resultado contém somente um prefixo cuja completude está comprovada. `verifiedThrough` é o último dia determinado da janela, mesmo se não houver ocorrência nesse dia. `null` significa que nem o primeiro dia foi coberto. Datas RDATE posteriores a esse prefixo ficam retidas. Uma saída parcial vazia não comprova um conjunto completo vazio.

O limite de resultados incide sobre a união segura já ordenada, após EXDATE. Se há uma ocorrência adicional além do teto, a saída é truncada e a cobertura recua até o dia anterior à primeira ocorrência omitida. Atingir exatamente o teto pode ser completo quando não existe resultado adicional. Isso também vale para `max_occurrences=0`.

## Relatório estruturado

Os campos aparecem nesta ordem estável:

| Campo | Conteúdo |
| --- | --- |
| `schemaVersion` | Inteiro `1`. |
| `status` | `complete` ou `incomplete`. |
| `complete` | Booleano correspondente ao status. |
| `stopReason` | `null`, `period_budget`, `day_budget` ou `result_limit`. |
| `window` | `start`, `end` e `inclusive: true`. |
| `verifiedThrough` | Data final do prefixo determinado, ou `null`. Quando completo, igual ao fim da janela. |
| `series` | `dtstart`, `rrule` canônica ou `null`, `rdates` e `exdates` normalizados. |
| `limits` | `maxPeriods`, `maxDays`, `maxOccurrences`. |
| `stats` | Métricas da execução corrente, detalhadas abaixo. |
| `occurrences` | Lista cronológica sem duplicatas de objetos `date` e `sources`. |

`stats` contém:

| Campo | Significado |
| --- | --- |
| `periodsEvaluated` | Períodos completos analisados durante a enumeração. |
| `daysExamined` | Dias desses períodos, dentro de `maxDays`. |
| `validationDays` | Custo separado de sincronização de DTSTART, entre 0 e 366. |
| `ruleOccurrencesConsumed` | Ocorrências consumidas pela RRULE desde DTSTART, inclusive antes da janela e antes de EXDATE. Não inclui datas posteriores ao fim da janela ou UNTIL. |
| `resultsEmitted` | Tamanho de `occurrences`. |

O custo observado em dias é `validationDays + daysExamined`. As métricas descrevem esta expansão delimitada, não toda uma série sem término.

Cada ocorrência tem a forma:

```json
{"date": "2026-01-31", "sources": ["dtstart", "rrule"]}
```

As origens efetivas são somente `dtstart`, `rrule` e `rdate`, sempre nessa ordem, sem repetições. Uma data adicionada por várias origens aparece uma única vez. Datas excluídas não são emitidas.

## Apresentações

Os três renderizadores aceitam relatórios do engine, verificam sua forma fechada e produzem erro sanitizado `invalid_report` em uso incorreto. Não recalculam a recorrência e não funcionam como validadores independentes de resultados fabricados por terceiros. Não alteram o relatório recebido.

- JSON: indentação de dois espaços, ordem estável e LF final; sem timestamp ou caminho da origem.
- Markdown: explica perfil, janela inclusiva, cobertura, razão de parada, regra canônica, exceções, orçamentos, estatísticas e tabela de datas/origens. Distingue saída parcial vazia de janela completa vazia.
- CSV: cabeçalho `data,origens`, todas as células entre aspas e linhas CRLF. Origens são unidas por vírgula dentro da célula: `"2026-01-31","dtstart,rrule"`. As únicas células de dados vêm de datas e identificadores protocolares validados, sem texto livre. O CSV não carrega o status de cobertura: use também o código de saída da CLI ou o relatório JSON/Markdown para determinar completude.

Relatórios podem revelar DTSTART, datas de inclusão e exclusão, inclusive fora da janela na seção `series`. Não são anônimos.

## CLI e arquivos

```sh
recorrencia-civil entrada.json
recorrencia-civil entrada.json --format markdown --output relatorio-novo.md
recorrencia-civil - --max-periods 0 --format csv < entrada.json
python -m recorrencia_civil entrada.json --max-days 10000 --max-occurrences 500
```

`FILE` é obrigatório. `-` permite stdin explicitamente; nenhum relógio ou caminho padrão preenche a origem. Arquivos locais são abertos para leitura e precisam ser arquivos regulares, verificados por `fstat` no descritor aberto. FIFO é recusado sem bloquear a abertura. O conteúdo da origem não é alterado.

Sem `--output`, o relatório vai para stdout em UTF-8, preservando LF no JSON/Markdown e CRLF no CSV também no Windows, com flush protegido. Falha de escrita ou pipe fechado resulta em erro. `--output NEW` exige um destino novo em diretório já existente: a CLI escreve um temporário no mesmo diretório, faz flush e `fsync`, e publica com link exclusivo. Não há fallback de sobrescrita. Se outro processo cria o destino durante a publicação, o arquivo dele é preservado e somente o temporário da operação é removido. Usar a própria origem como destino falha preservando-a.

| Código de saída | Significado |
| --- | --- |
| `0` | Expansão completa; também `--help` e `--version`. |
| `2` | Expansão incompleta; o relatório contém somente o prefixo comprovado. |
| `3` | Erro de argumentos, perfil, JSON, leitura, escrita ou publicação. |

Diagnósticos vão para stderr, sem ecoar caminho absoluto, argumentos crus ou JSON rejeitado. Códigos operacionais adicionais incluem `input_read`, `input_type`, `input_size`, `input_encoding`, `output_exists` e `output_write`. Falha na publicação não transforma o destino em arquivo parcial.
