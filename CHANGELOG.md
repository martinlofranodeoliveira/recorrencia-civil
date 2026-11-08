# Histórico de alterações

## 1.0.0 — 2026-11-08

Primeira versão do perfil Recorrência Civil descrito em [SPEC.md](SPEC.md).

- API Python `expand` e `expand_document`, com datas civis de 0001 a 9999 e janelas inclusivas explícitas.
- Regras `DAILY`, `WEEKLY`, `MONTHLY` e `YEARLY`, intervalos, `COUNT`/`UNTIL`, seletores de mês, dia e posição e início de semana configurável.
- Seleção de períodos completos, sincronização de `DTSTART`, descarte de datas inexistentes e interpretação declarada dos ordinais anuais.
- União de `DTSTART`, RRULE e RDATE, exclusões por EXDATE e origens ordenadas por ocorrência.
- Orçamentos de períodos, dias e resultados, custo de validação separado e relatórios com prefixo comprovado e motivo de interrupção.
- Relatórios determinísticos em JSON, Markdown e CSV; CLI com leitura limitada e publicação exclusiva de arquivos novos.
- Testes sintéticos e comparações com `python-dateutil==4.0.0` como oráculo de desenvolvimento, sem dependência externa no runtime.
- Documentação em português e licença MIT.

Esta entrada descreve o conteúdo da versão; não afirma publicação em serviço de pacotes, adoção por terceiros ou validação em produção.
