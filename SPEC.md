# Recorrência Civil 1.0.0 · contrato

Biblioteca e CLI offline para conjuntos de datas civis. Implementação própria; python-dateutil é apenas oráculo de desenvolvimento. O perfil cobre datas gregorianas 0001–9999, sem relógio implícito, horário, fuso, eventos, duração ou parser de calendários ICS. Base normativa: RFC 5545 §§3.3.10 e 3.8.5, consideradas as erratas verificadas 1913, 3779 e 3747. Não alegar conformidade integral iCalendar.

## Entrada

API pública `expand(series, window_start, window_end, *, limits=ExpansionLimits()) -> dict`.

`series` é dict simples com `dtstart` obrigatório e somente `rrule`, `rdates`, `exdates` opcionais. Datas são strings ASCII exatas `YYYY-MM-DD`. `rrule` é string ou null (default null), RDATE/EXDATE são listas (default vazias), cada uma com até 1000 datas antes de deduplicar. Duplicatas são aceitas e normalizadas em ordem. Rejeitar subclasses, campos extras, tipos errados e datetime. A API não altera argumentos.

Documento CLI/`expand_document`:

```json
{"schemaVersion":1,"series":{"dtstart":"2026-01-31","rrule":"FREQ=MONTHLY;COUNT=4","rdates":[],"exdates":[]},"window":{"start":"2026-01-01","end":"2026-12-31"}}
```

Chaves do documento e window são exatas e obrigatórias; `schemaVersion` inteiro 1 (não boolean). Entrada JSON até 65536 bytes UTF-8, sem BOM, duplicate keys, NaN/Infinity ou dados após o JSON. API de dict aplica limites estruturais antes de percorrer listas grandes. As pontas da janela são **inclusivas**, start <= end. Uma janela não reinicia COUNT nem muda BYSETPOS.

## RRULE

Até 1024 caracteres ASCII, sem whitespace, prefixo `RRULE:`, line folding ou linha ICS. Nomes e valores protocolares não diferenciam caixa; ordem das partes livre. Partes duplicadas e desconhecidas são erros. FREQ obrigatório: DAILY, WEEKLY, MONTHLY, YEARLY.

| Parte | Perfil |
| --- | --- |
| INTERVAL | dígitos, inteiro 1–9999; default 1 |
| COUNT | dígitos, inteiro 1–1000000; mutuamente exclusivo com UNTIL |
| UNTIL | DATE `YYYYMMDD`, inclusivo, >= DTSTART; DATE-TIME fora do perfil |
| BYMONTH | lista 1–12 |
| BYMONTHDAY | lista assinada -31…-1 ou 1…31; proibida com WEEKLY |
| BYDAY | MO,TU,WE,TH,FR,SA,SU, com ordinal opcional ±1…53 somente MONTHLY/YEARLY |
| BYSETPOS | lista assinada ±1…366, exige outra parte BY |
| WKST | weekday sem ordinal; default MO |

COUNT >=1, seus tetos e UNTIL >= DTSTART são restrições declaradas deste perfil. Não rotular todo iCalendar fora do perfil como inválido. Listas aceitam zeros à esquerda e sinal + onde a gramática permite sinal; normalizam por valor sem mudar semântica. Nenhuma lista vazia. Controles, caracteres não ASCII e partes de tempo/BYWEEKNO/BYYEARDAY/RSCALE/BYEASTER são recusados explicitamente.

Regra canônica: FREQ;INTERVAL;COUNT ou UNTIL se presentes;BYMONTH;BYMONTHDAY;BYDAY;BYSETPOS;WKST. Defaults INTERVAL/WKST sempre escritos. Listas numéricas únicas ordenadas; BYDAY ordenado por weekday e depois ordinal (ausente antes dos ordinais); ordinal positivo sem +, datas UNTIL básicas.

## Expansão

- Intervalos começam no dia DTSTART (DAILY), na semana que o contém segundo WKST (WEEKLY), no primeiro dia do mês (MONTHLY) ou 1 de janeiro (YEARLY). INTERVAL salta essas unidades; não clampa dia 31 ou 29/02 em mês/ano incompatível.
- Candidatos são dias válidos do período completo, limitados ao domínio 0001–9999. Aplicar BYMONTH, BYMONTHDAY, BYDAY e depois BYSETPOS; posições positivas/negativas incidem sobre lista cronológica única do **período completo**, antes de cortar <DTSTART, UNTIL ou janela.
- Defaults: WEEKLY sem BYDAY usa weekday de DTSTART. MONTHLY sem BYMONTHDAY nem BYDAY usa dia de DTSTART. YEARLY sem BYMONTHDAY nem BYDAY usa dia de DTSTART e, se BYMONTH ausente, mês de DTSTART. YEARLY com BYMONTHDAY ou BYDAY e sem BYMONTH expande em todos os meses pertinentes, sem herdar mês implicitamente.
- BYDAY com ordinal é relativo ao mês em MONTHLY e em YEARLY com BYMONTH; em YEARLY sem BYMONTH, relativo ao ano. Com vários BYDAY, basta satisfazer um; com BYMONTHDAY e BYDAY, ambas as partes devem ser satisfeitas.
- DTSTART deve pertencer aos candidatos selecionados do primeiro período (e ser <= UNTIL). Se não, lançar `RecurrenceError` com code `dtstart_mismatch`: o padrão RFC fica indefinido, não inventar uma expansão.
- COUNT conta ocorrências da RRULE desde DTSTART, antes de EXDATE e janela. Data inválida não conta. RDATE não consome COUNT e não é cortado por UNTIL.
- Resultado final é união de DTSTART, RRULE e RDATE, menos EXDATE, sem duplicatas. EXDATE pode remover DTSTART, preservando sua função de âncora. RDATE anterior a DTSTART é aceito como união explícita deste perfil, sem promessa de serializar um componente iCalendar completo.

## Limites e cobertura

`ExpansionLimits(max_periods=10000,max_days=100000,max_occurrences=5000)`, inteiros exatos (bool rejeitado), zero permitido. Tetos 100000, 1000000 e 100000 respectivamente. Sem deadline, garantia de memória nativa ou otimização obrigatória para saltar até uma janela distante.

Primeiro validar sincronização de DTSTART examinando no máximo um período (até **366 dias**). Esse custo fixo vai para `validationDays`, separado do orçamento de enumeração. Cada período da enumeração é atômico: reservar seu número real de dias válidos do domínio antes de examiná-lo. Se orçamento não permite período inteiro, não consumir parte nem suas correspondências. `daysExamined` não ultrapassa max_days; soma com validationDays explicita o custo observado. Não calcular BYSETPOS em período parcial.

Ao parar por orçamento, emitir somente o prefixo global cuja ausência de outras ocorrências está comprovada. `verifiedThrough` é o último dia da janela cuja expansão completa foi determinada; null se nem o primeiro dia foi coberto. Até um período não processado, o limite seguro é o dia anterior ao menor dia RRULE possível desse período (nunca antes de DTSTART). RDATEs conhecidos depois desse limite ficam retidos para preservar prefixo. Não chamar saída vazia parcial de conjunto completo vazio.

O limite de resultados é aplicado à união já segura e ordenada. Se existir um resultado adicional além do teto, truncar a saída e reduzir verifiedThrough ao dia anterior à primeira ocorrência omitida; stopReason `result_limit`. Se a saída contém exatamente o teto mas não há resultado adicional, pode ser complete. Zero resultados comporta-se da mesma forma. Quando a RRULE acaba por COUNT/UNTIL/domínio ou o próximo período está além da janela, todas as datas explícitas da janela são conhecidas; cobertura completa salvo limite de resultados.

## Relatório

Campos em ordem estável:

```
schemaVersion:1
status:"complete"|"incomplete"
complete:boolean
stopReason:null|"period_budget"|"day_budget"|"result_limit"
window:{start:"YYYY-MM-DD",end:"YYYY-MM-DD",inclusive:true}
verifiedThrough:"YYYY-MM-DD"|null
series:{dtstart,rrule:canônica|null,rdates:[...],exdates:[...]}
limits:{maxPeriods,maxDays,maxOccurrences}
stats:{periodsEvaluated,daysExamined,validationDays,ruleOccurrencesConsumed,resultsEmitted}
occurrences:[{date:"YYYY-MM-DD",sources:["dtstart","rrule","rdate"]}]
```

sources só contém origens efetivas, nessa ordem. COUNT consumido inclui exclusões e datas antes da janela, mas não datas RRULE posteriores ao fim da janela ou UNTIL. Todo relatório complete tem verifiedThrough igual ao fim da janela. Métricas são da execução corrente, não de toda série infinita. JSON indentado 2 espaços + LF final, Markdown e CSV também determinísticos. Relatórios podem revelar datas da série, inclusive exceções; não são anônimos. Sem timestamp ou caminho absoluto da origem.

## Módulos e contratos internos

`model.py`: RecurrenceError(code,message), ExpansionLimits, DaySpec(weekday:int,ordinal:int|None), Rule(frequency,interval,count,until,bymonth,bymonthday,byday,bysetpos,week_start,canonical), Series(dtstart,rule,rdates,exdates); dataclasses internas congeladas, datas datetime.date.

`parser.py`: `parse_date(value)`; `parse_series(dict)->Series` (sintaxe/tipos, sincronização fica no engine); `series_dict(Series)->dict`; `parse_document(dict)->(Series,date,date)`; `load_document(text)->dict` com JSON estrito. Métodos não repetem valores rejeitados nas mensagens.

`engine.py`: `expand_series(series:Series,start:date,end:date,limits:ExpansionLimits)->dict` implementa a semântica acima. Recebe apenas objetos internos já validados; não importa dateutil. Pode importar series_dict para construir relatório.

`api.py`: wrappers públicos `expand`, `expand_document`, chamam parser e engine. `__init__.py` exporta wrappers, ExpansionLimits, RecurrenceError, to_json/to_markdown/to_csv e __version__.

`report.py`: `to_json(report)`, `to_markdown(report)`, `to_csv(report)`. Saídas só para relatórios produzidos pelo engine; erro de forma sanitizado em uso incorreto. CSV cabeçalho `data,origens`, CRLF e aspas em todas as células; nenhuma fórmula originada de texto livre. Markdown explica cobertura/razão e inclui regra canônica e tabela de datas/origens. Não insinuar fuso ou execução de agenda.

`cli.py`: `main(argv=None)`. `recorrencia-civil FILE` ou `-` para stdin, `--format json|markdown|csv`, `--output NEW`, `--max-periods`, `--max-days`, `--max-occurrences`. Entrada leitura limitada efetiva +1 byte, inclusive FIFO não bloqueante? Origem de arquivo deve ser arquivo regular verificado por fstat; stdin explícito permitido. Saída em novo arquivo com publicação exclusiva/temp+fsync, não sobrescrever em corrida e não remover destino alheio. Stdout com flush protegido, falha de pipe retorna erro. Erros sanitizados sem ecoar caminho absoluto, JSON rejeitado ou argumentos crus.

Exit 0 complete/help/version; 2 incomplete; 3 erro de argumentos, perfil, JSON, IO ou publicação. Não importar dependências dev no runtime. Versão pública MIT, Python>=3.11, sem publicação PyPI, README em português, wheel/sdist/ZIP de fontes e checksums.
