# Como contribuir

Contribuições são bem-vindas por issue ou pull request no [repositório](https://github.com/martinlofranodeoliveira/recorrencia-civil). Para problemas sensíveis, siga [SECURITY.md](SECURITY.md). Use exemplos sintéticos e evite calendários, caminhos e dados pessoais de clientes.

## Ambiente

Use Python 3.11 ou superior. Na raiz do clone:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m unittest discover -s tests -v
python scripts/check_oracles.py
```

No PowerShell, a ativação é `.venv\Scripts\Activate.ps1`. As versões das ferramentas estão fixadas em [pyproject.toml](pyproject.toml), incluindo `python-dateutil==4.0.0` para o oráculo. O pacote instalado sem o extra `dev` não depende de dateutil. Não importe dependências de desenvolvimento nos módulos de runtime.

O comando do oráculo compara fixtures sintéticas independentes com a API de dateutil e imprime um resumo determinístico. Ele exige a versão fixada. O adaptador usa `datetime` apenas para consultar o oráculo; isso não acrescenta horários ou fusos ao perfil público. Resultados do oráculo são evidência dos casos executados, não uma certificação do padrão ou de uso em produção.

Para construir wheel e sdist:

```bash
python -m build
```

A construção gera artefatos em `dist/`. Construir localmente não publica no PyPI, no GitHub ou em outro serviço. A distribuição do projeto é por fontes e artefatos de Release; alterações de metadados devem preservar essa orientação.

## Mudanças de comportamento

Leia [SPEC.md](SPEC.md) antes de alterar parser, engine ou relatório. Descreva no pull request uma entrada concreta, o comportamento anterior e o resultado esperado. Adicione uma reprodução pequena que verifique o comportamento relevante. Mudanças na interface, no perfil ou no esquema precisam atualizar a especificação e a documentação correspondente.

Preserve especialmente:

- Datas civis no domínio 0001–9999, sem relógio ou fuso implícito.
- Sincronização estrita de `DTSTART` e erro `dtstart_mismatch` quando ela falhar.
- `COUNT` global antes de exclusões e janela; `RDATE` não consome esse contador.
- Filtros e `BYSETPOS` sobre o período completo antes dos cortes temporais.
- Reserva atômica de períodos, `validationDays` separado e prefixo global comprovado.
- Ordem estável das origens, ausência de mutação dos argumentos e saída determinística.
- Validação limitada das entradas, mensagens sanitizadas e publicação exclusiva de arquivos novos.

O perfil é deliberadamente menor que iCalendar. Não chame uma entrada fora dele de inválida em todo o padrão. Se uma mudança se apoiar na RFC, inclua a seção e as erratas relevantes. Use [RFC 5545](https://www.rfc-editor.org/rfc/rfc5545.html), [errata 1913](https://www.rfc-editor.org/errata/eid1913), [errata 3779](https://www.rfc-editor.org/errata/eid3779) e [errata 3747](https://www.rfc-editor.org/errata/eid3747) como fontes primárias.

Relate quais verificações foram realmente executadas, com ambiente e resultado. Não atribua à CI, a usuários ou à produção uma validação que não foi observada. Evite incluir arquivos de ambiente virtual, caches, relatórios privados ou credenciais na contribuição.

## Licença

Contribuições de código e documentação devem poder ser distribuídas sob a [licença MIT](LICENSE) deste projeto. Preserve avisos e permissões de componentes adaptados. Registre novas atribuições e ferramentas em [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), com origem, versão e licença quando aplicável.
