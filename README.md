# Recorrência Civil

Biblioteca Python e CLI para expandir conjuntos de **datas civis**, com janela inclusiva, exceções e limites explícitos. A versão `1.0.0` trabalha offline com datas gregorianas de `0001-01-01` a `9999-12-31`, sem dependências externas de execução.

Uma regra mensal no dia 31 pode produzir janeiro, março, maio e julho, pulando os meses que não têm esse dia. O relatório informa as datas e até onde o resultado está comprovado quando o orçamento termina.

O [contrato completo está em SPEC.md](SPEC.md). Este é um perfil de recorrência baseado na RFC 5545: não importa arquivos ICS, não modela horários, fusos, eventos ou duração, não consulta o relógio e não executa uma agenda. Não há alegação de conformidade integral iCalendar.

## Instalação

Requer Python **3.11 ou superior**. Instale a partir das fontes ou de um wheel disponibilizado em uma Release do repositório; o pacote não é distribuído pelo PyPI.

```bash
git clone https://github.com/martinlofranodeoliveira/recorrencia-civil.git
cd recorrencia-civil
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
recorrencia-civil --version
```

No Windows, ative o ambiente com `.venv\Scripts\Activate.ps1` no PowerShell. Para instalar um wheel, baixe o arquivo correspondente pela página de [Releases](https://github.com/martinlofranodeoliveira/recorrencia-civil/releases) e, no ambiente virtual, use:

```bash
python -m pip install ./recorrencia_civil-1.0.0-py3-none-any.whl
```

Confira o SHA-256 do artefato com o manifesto `SHA256SUMS` fornecido junto à Release, por exemplo com `sha256sum -c SHA256SUMS` no diretório dos downloads. A instalação por fontes pode baixar ferramentas de construção; a expansão de datas usa somente a biblioteca padrão do Python e não precisa de rede.

## Primeiro exemplo pela API

```python
from recorrencia_civil import expand

report = expand(
    {"dtstart": "2026-01-31", "rrule": "FREQ=MONTHLY;COUNT=4"},
    "2026-01-01",
    "2026-12-31",
)

print([item["date"] for item in report["occurrences"]])
# ['2026-01-31', '2026-03-31', '2026-05-31', '2026-07-31']
print(report["complete"], report["verifiedThrough"])
# True 2026-12-31
```

As duas pontas da janela são **inclusivas**. A regra é ancorada em `dtstart`; a janela recorta o resultado sem reiniciar `COUNT`.

Para o último dia de segunda a sexta de cada mês, use `FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1`, com um `dtstart` que satisfaça a regra, por exemplo `2026-01-30`. Feriados não são inferidos. Uma exceção remove a data selecionada; não a transfere automaticamente para o dia anterior.

## Documento e CLI

Salve este documento UTF-8 sem BOM como `serie.json`:

```json
{
  "schemaVersion": 1,
  "series": {
    "dtstart": "2026-01-31",
    "rrule": "FREQ=MONTHLY;COUNT=4",
    "rdates": ["2026-02-10"],
    "exdates": ["2026-03-31"]
  },
  "window": {
    "start": "2026-01-01",
    "end": "2026-12-31"
  }
}
```

```bash
recorrencia-civil serie.json
recorrencia-civil serie.json --format markdown
recorrencia-civil serie.json --format csv --output resultado.csv
recorrencia-civil serie.json --max-periods 2 --max-days 100 --max-occurrences 10
python -m recorrencia_civil serie.json
```

`--output NEW` exige um **arquivo novo** e um diretório pai existente. O publicador grava um temporário, sincroniza o arquivo e publica por link exclusivo; um destino que já existe, inclusive criado durante a operação, não é sobrescrito. Sistemas de arquivos sem o mecanismo necessário retornam erro. Sem `--output`, o relatório vai para stdout.

Use `-` para autorizar a leitura de stdin explicitamente:

```bash
recorrencia-civil - --format json < serie.json
```

Arquivos de origem devem ser regulares. A entrada JSON tem limite de **65.536 bytes** e recusa chaves duplicadas, BOM, NaN/Infinity ou dados após o documento. O objeto de documento e a janela exigem exatamente as chaves mostradas. Em `series`, só `dtstart` é obrigatório; os demais campos têm os defaults documentados abaixo.

| Código de saída | Significado |
| --- | --- |
| `0` | Relatório completo, ajuda ou versão. |
| `2` | Relatório válido, mas incompleto por limite. |
| `3` | Erro de argumentos, perfil, JSON, leitura ou escrita. |

Mesmo com código `2`, o relatório contém um prefixo comprovado e pode ter sido escrito em `--output`. Consulte `complete`, `stopReason` e `verifiedThrough` antes de usar a lista como conjunto completo.

Os arquivos de demonstração usam apenas datas sintéticas:

| Arquivo | Conteúdo |
| --- | --- |
| [ultimo-dia-util.json](examples/ultimo-dia-util.json) | Último dia de segunda a sexta, com uma exclusão e uma inclusão explícita. |
| [ultimo-dia-util-result.json](examples/ultimo-dia-util-result.json), [Markdown](examples/ultimo-dia-util-result.md) e [CSV](examples/ultimo-dia-util-result.csv) | O mesmo relatório em três formatos. |
| [dia-31.json](examples/dia-31.json) | Meses incompatíveis pulados sem ajustar a data. |
| [consulta-parcial.json](examples/consulta-parcial.json) | Entrada para explorar limites e cobertura parcial. |
| [oraculos.json](examples/oraculos.json) | Resumo reproduzível das comparações de desenvolvimento e da divergência conhecida. |

## Série, união e exclusões

A API aceita um `dict` simples com `dtstart` obrigatório, `rrule` opcional (`null` por padrão), `rdates` e `exdates` opcionais (listas vazias por padrão). As datas são strings ASCII exatas `YYYY-MM-DD`; objetos `date`/`datetime`, subclasses, campos extras e tipos incompatíveis são recusados. Cada lista explícita aceita até 1.000 entradas antes de deduplicar e ordenar. Os argumentos não são alterados.

O conjunto final é a união de `DTSTART`, ocorrências da `RRULE` e `RDATE`, menos `EXDATE`. Duplicatas viram uma data com as origens efetivas, na ordem `dtstart`, `rrule`, `rdate`. `EXDATE` prevalece sobre todas as origens e pode remover `DTSTART`, que continua sendo a âncora.

`COUNT` conta ocorrências da regra desde `DTSTART`, antes das exclusões e do recorte da janela. `RDATE` não consome `COUNT` e não é cortado por `UNTIL`. Este perfil aceita `RDATE` anterior a `DTSTART` como união explícita, sem prometer serialização de um componente iCalendar completo.

`DTSTART` precisa pertencer aos candidatos selecionados do primeiro período. Se não pertencer, a API lança `RecurrenceError` com `code == "dtstart_mismatch"`; ela não inventa uma expansão para o caso indefinido no padrão.

## Perfil de RRULE

A regra de entrada tem até 1.024 caracteres ASCII, sem whitespace, prefixo `RRULE:`, quebra de linha ou linha ICS. A inclusão de defaults na forma canônica do relatório pode ampliar esse texto até 1.043 caracteres; isso não aumenta o teto da entrada bruta. Nomes e valores protocolares não diferenciam caixa. Partes repetidas ou desconhecidas são recusadas.

| Parte | Valores aceitos |
| --- | --- |
| `FREQ` | Obrigatório: `DAILY`, `WEEKLY`, `MONTHLY` ou `YEARLY`. |
| `INTERVAL` | `1` a `9999`; default `1`. |
| `COUNT` | `1` a `1000000`; exclusivo com `UNTIL`. |
| `UNTIL` | Data básica `YYYYMMDD`, inclusiva e igual ou posterior a `DTSTART`. |
| `BYMONTH` | Lista de meses `1` a `12`. |
| `BYMONTHDAY` | Lista de `-31` a `-1` ou `1` a `31`; proibida com `WEEKLY`. |
| `BYDAY` | `MO,TU,WE,TH,FR,SA,SU`; ordinal de `±1` a `±53` somente com `MONTHLY`/`YEARLY`. |
| `BYSETPOS` | Lista de `±1` a `±366`; exige outra parte `BY`. |
| `WKST` | Dia da semana sem ordinal; default `MO`. |

As listas são normalizadas por valor. Partes de tempo, `BYWEEKNO`, `BYYEARDAY`, `RSCALE` e `BYEASTER` estão fora do perfil. Esses limites são decisões deste projeto: uma construção recusada aqui pode existir em outros perfis iCalendar.

Os períodos começam no dia de `DTSTART` para `DAILY`, na semana que o contém segundo `WKST` para `WEEKLY`, no primeiro dia do mês para `MONTHLY` e em 1º de janeiro para `YEARLY`. `INTERVAL` salta essas unidades. Datas inexistentes são puladas e não consomem `COUNT`: dia 31 não vira dia 30, e 29 de fevereiro não vira 28.

Sem seletores de dia, `WEEKLY` usa o dia da semana de `DTSTART`; `MONTHLY` usa seu dia do mês; `YEARLY` usa seu dia e, se `BYMONTH` estiver ausente, seu mês. Em `YEARLY`, `BYMONTHDAY` ou `BYDAY` sem `BYMONTH` expande nos meses pertinentes do ano, sem herdar implicitamente o mês de `DTSTART`.

Ordinais de `BYDAY` são relativos ao mês em `MONTHLY` e em `YEARLY` com `BYMONTH`; em `YEARLY` sem `BYMONTH`, são relativos ao ano. Vários valores de `BYDAY` são alternativas. `BYMONTHDAY` e `BYDAY`, quando presentes juntos, devem ser satisfeitos simultaneamente.

Os filtros são aplicados ao **período completo**, e então `BYSETPOS` seleciona posições da lista cronológica única. Só depois são cortadas as datas anteriores a `DTSTART`, posteriores a `UNTIL` ou fora da janela. Mudar a janela não muda o significado de uma posição.

A forma canônica inclui sempre `INTERVAL` e `WKST`, ordena listas e usa a ordem `FREQ;INTERVAL;COUNT/UNTIL;BYMONTH;BYMONTHDAY;BYDAY;BYSETPOS;WKST`. Por exemplo: `FREQ=MONTHLY;INTERVAL=1;COUNT=4;WKST=MO`.

## Limites e cobertura comprovada

```python
from recorrencia_civil import ExpansionLimits, expand

partial = expand(
    {
        "dtstart": "2026-01-01",
        "rrule": "FREQ=DAILY",
        "rdates": ["2026-01-20"],
    },
    "2026-01-01",
    "2026-01-31",
    limits=ExpansionLimits(max_periods=2),
)

assert partial["complete"] is False
assert partial["stopReason"] == "period_budget"
assert partial["verifiedThrough"] == "2026-01-02"
assert [item["date"] for item in partial["occurrences"]] == [
    "2026-01-01", "2026-01-02"
]
```

O `RDATE` de 20 de janeiro é conhecido, mas fica retido porque está além do prefixo comprovado. Isso preserva uma lista que pode ser usada como prefixo do resultado global ordenado.

| API / CLI | Default | Teto | Unidade |
| --- | --- | --- | --- |
| `max_periods` / `--max-periods` | `10000` | `100000` | Períodos avaliados. |
| `max_days` / `--max-days` | `100000` | `1000000` | Dias reais dos períodos avaliados. |
| `max_occurrences` / `--max-occurrences` | `5000` | `100000` | Datas da união segura emitida. |

Os três valores aceitam **zero**, exigem inteiros exatos e recusam booleanos. A sincronização de `DTSTART` é validada antes da enumeração, examinando até um período, com no máximo **366 dias**. Esse custo aparece em `stats.validationDays`, separado de `stats.daysExamined` e do orçamento `max_days`. Sem regra, `validationDays` é zero.

Cada período da enumeração é atômico: seus dias precisam caber integralmente nos orçamentos. Não se examina parte de um mês ou ano para obter um `BYSETPOS` parcial. O custo observado em dias é `validationDays + daysExamined`; não há deadline nem garantia de memória nativa, e uma janela distante pode exigir enumeração desde a âncora.

| Campo | Como interpretar |
| --- | --- |
| `status` / `complete` | `complete`/`true` comprova toda a janela; `incomplete`/`false` comprova somente o prefixo indicado. |
| `stopReason` | `null`, `period_budget`, `day_budget` ou `result_limit`. |
| `verifiedThrough` | Último dia inclusivo comprovado; `null` se nem o primeiro dia da janela foi coberto. Em relatório completo, é o fim da janela. |
| `occurrences` | Datas únicas, ordenadas, com a lista de origens efetivas. |
| `stats.ruleOccurrencesConsumed` | Ocorrências da regra consumidas nesta execução, incluindo exclusões e datas antes da janela; não inclui datas posteriores ao fim da janela ou a `UNTIL`. |

Uma lista vazia **incompleta** não comprova ausência de datas na janela. Com zero períodos e uma regra que começa no início da janela, por exemplo, a lista pode estar vazia com `verifiedThrough: null`. Uma lista vazia **completa** comprova que não restaram datas após união e exclusões em toda a janela.

O limite de resultados só trunca quando existe uma ocorrência adicional segura além do teto. Se há exatamente o teto e nenhuma adicional, o relatório pode ser completo. Se há uma omitida, `verifiedThrough` recua para o dia anterior à primeira omitida e `stopReason` é `result_limit`. A regra vale também para teto zero. Ao acabar por `COUNT`, `UNTIL` ou domínio, ou quando o próximo período fica além da janela, datas explícitas tardias tornam-se seguras, salvo limite de resultados.

## API e formatos

A interface pública exporta `expand`, `expand_document`, `ExpansionLimits`, `RecurrenceError`, `to_json`, `to_markdown`, `to_csv` e `__version__`.

```python
from recorrencia_civil import expand_document, to_json, to_markdown, to_csv

report = expand_document({
    "schemaVersion": 1,
    "series": {"dtstart": "2026-01-31", "rrule": "FREQ=MONTHLY;COUNT=4"},
    "window": {"start": "2026-01-01", "end": "2026-12-31"},
})
json_text = to_json(report)
markdown_text = to_markdown(report)
csv_text = to_csv(report)
```

Os formatadores recebem relatórios produzidos pelo engine. JSON usa indentação de dois espaços e LF final. Markdown inclui cobertura, regra canônica e tabela de datas/origens. CSV tem cabeçalho `data,origens`, terminações CRLF e todas as células entre aspas. Ele contém somente linhas de datas e origens, sem o status de cobertura; preserve também o JSON ou confira o código de saída da CLI antes de tratá-lo como conjunto completo. Os resultados são determinísticos para os mesmos argumentos: não contêm timestamp nem caminho absoluto da origem.

Os relatórios incluem a série normalizada, inclusive datas de exceção. Eles **não são anônimos**; revise o conteúdo antes de compartilhar. Veja [SECURITY.md](SECURITY.md).

## Desenvolvimento e referências

Consulte [CONTRIBUTING.md](CONTRIBUTING.md) para preparar o ambiente, executar testes e construir artefatos. O engine é uma implementação própria; `python-dateutil==4.0.0` é usado somente como oráculo de desenvolvimento, fora do runtime. Os exemplos e fixtures são sintéticos; não representam calendários de clientes nem evidência de adoção ou validação em produção.

Há uma divergência reproduzida com dateutil `4.0.0` na primeira semana de `FREQ=WEEKLY;COUNT=3;BYDAY=MO,TH;BYSETPOS=2;WKST=MO`, com `DTSTART=2026-01-08`. Este perfil seleciona posições na semana completa e só depois corta datas anteriores à âncora. Dateutil seleciona na primeira semana parcial. Na união `DTSTART ∪ RRULE`, para janeiro de 2026:

| Implementação | Datas |
| --- | --- |
| Recorrência Civil | `2026-01-08`, `2026-01-15`, `2026-01-22` |
| dateutil 4.0.0 | `2026-01-08`, `2026-01-15`, `2026-01-22`, `2026-01-29` |

O caso é registrado separadamente em [oraculos.json](examples/oraculos.json), sem tratá-lo como comparação que passou. Na verificação de 08/11/2026, a discussão permanecia na [issue upstream 1398](https://github.com/dateutil/dateutil/issues/1398) e na [proposta de alteração 1575](https://github.com/dateutil/dateutil/pull/1575). A existência da proposta não significa que a mudança tenha sido aceita ou incorporada ao oráculo. A referência para o comportamento deste perfil continua sendo o período completo definido em SPEC.md e a [RFC 5545 §3.3.10](https://www.rfc-editor.org/rfc/rfc5545.html#section-3.3.10).

O perfil usa a [RFC 5545, seção 3.3.10](https://www.rfc-editor.org/rfc/rfc5545.html#section-3.3.10) e as [propriedades de recorrência da seção 3.8.5](https://www.rfc-editor.org/rfc/rfc5545.html#section-3.8.5), consideradas as erratas verificadas [1913](https://www.rfc-editor.org/errata/eid1913), [3779](https://www.rfc-editor.org/errata/eid3779) e [3747](https://www.rfc-editor.org/errata/eid3747). As duas primeiras esclarecem os ordinais anuais de `BYDAY`; a última corrige as notas de expansão e limitação. Os detalhes aceitos pela biblioteca estão fixados em [SPEC.md](SPEC.md).

Código e documentação sob a [licença MIT](LICENSE). As atribuições de código adaptado e ferramentas estão em [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Alterações da versão estão em [CHANGELOG.md](CHANGELOG.md).
