# Autoria e avisos de componentes

O código e a documentação originais de Recorrência Civil são distribuídos sob a [licença MIT](LICENSE), com `Copyright (c) 2026 Contribuidores da LOFRANO TECNOLOGIA`.

## Publicador de arquivos adaptado

O publicador de novos arquivos em `src/recorrencia_civil/cli.py`, função `_publish_new`, adapta mecanismos dos projetos da mesma família:

| Projeto de origem | Licença | Aviso preservado |
| --- | --- | --- |
| [EPUB Navigation Audit](https://github.com/martinlofranodeoliveira/epub-navigation-audit) | MIT | Copyright (c) 2026 Contribuidores da LOFRANO TECNOLOGIA |
| [SQLite Catalog Report](https://github.com/martinlofranodeoliveira/sqlite-catalog-report) | MIT | Copyright (c) 2026 Contribuidores da LOFRANO TECNOLOGIA |

O aviso de copyright e o texto de permissão aplicáveis estão preservados integralmente em [LICENSE](LICENSE). Preserve ambos ao redistribuir essas partes. A adaptação diz respeito à publicação exclusiva de arquivos; não incorpora a análise de EPUB ou de bancos SQLite desses projetos.

## Runtime

O pacote não tem dependências externas de execução e não inclui cópias vendorizadas de bibliotecas. Utiliza a instalação Python do usuário e módulos de sua biblioteca padrão, sujeitos aos [termos próprios do Python](https://docs.python.org/3/license.html). A licença MIT deste repositório não relicencia o runtime ou componentes fornecidos com ele.

O engine de recorrência é uma implementação própria. Código de dateutil não integra o engine nem é importado pelo runtime.

## Ferramentas de desenvolvimento e construção

| Ferramenta | Versão declarada | Uso | Licença/origem |
| --- | --- | --- | --- |
| `python-dateutil` | `4.0.0` | Oráculo independente para comparações sintéticas de desenvolvimento. | [BSD de três cláusulas e Apache 2.0, conforme os termos do projeto](https://github.com/dateutil/dateutil/blob/master/LICENSE). |
| `build` | `1.5.0` | Construção de wheel e sdist. | [MIT](https://github.com/pypa/build/blob/main/LICENSE). |
| `setuptools` | `84.2.1` | Backend de construção. | [MIT](https://github.com/pypa/setuptools/blob/main/LICENSE). |

As versões estão fixadas em [pyproject.toml](pyproject.toml). Essas ferramentas são obtidas e instaladas separadamente, não vendorizadas no runtime. Seus avisos e os de dependências transitivas permanecem aplicáveis às respectivas distribuições. Consulte os arquivos de licença do ambiente instalado antes de redistribuir as próprias ferramentas.

## Fontes normativas e exemplos

A documentação referencia a [RFC 5545](https://www.rfc-editor.org/rfc/rfc5545.html), em especial §§3.3.10 e 3.8.5, e as erratas verificadas [1913](https://www.rfc-editor.org/errata/eid1913), [3779](https://www.rfc-editor.org/errata/eid3779) e [3747](https://www.rfc-editor.org/errata/eid3747). O repositório não distribui uma cópia da RFC e não afirma certificação ou aprovação pela IETF ou pelo RFC Editor. O perfil aceito está definido em [SPEC.md](SPEC.md).

Exemplos, fixtures e relatórios de demonstração usam dados originais e sintéticos, sem calendários de clientes, dados pessoais ou alegações de adoção. As referências e ferramentas mantêm suas licenças e nomes próprios.
