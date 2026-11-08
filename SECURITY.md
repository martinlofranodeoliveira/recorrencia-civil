# Segurança

Esta política descreve a versão `1.0.0` de Recorrência Civil. O projeto não oferece prazo de resposta ou de correção garantido. Use uma instalação Python 3.11 ou superior com as atualizações de segurança fornecidas pelo seu distribuidor.

## Relatar um problema

Para uma falha que exponha dados, permita sobrescrita indevida ou ultrapasse os limites documentados, procure o canal de contato publicado no [site da LOFRANO TECNOLOGIA](https://lofranotecnologia.com.br) e solicite um meio privado para enviar os detalhes. Se o repositório disponibilizar o recurso privado de reporte de vulnerabilidades do GitHub, esse canal também pode ser usado. Não inclua segredos, calendários reais ou informações pessoais em uma issue pública.

Inclua a versão do pacote e do Python, o sistema operacional, um exemplo **sintético mínimo**, os limites usados e os passos de reprodução. Descreva o comportamento observado e o esperado. Falhas de semântica sem dados sensíveis podem ser relatadas nas [issues do projeto](https://github.com/martinlofranodeoliveira/recorrencia-civil/issues).

## Fronteiras do programa

A expansão é local e não acessa rede, relógio, calendários remotos ou executores de tarefas. O pacote não importa ICS, horários, fusos, expressões Python ou plugins a partir da entrada. O runtime usa somente a biblioteca padrão do Python; as ferramentas de construção e o oráculo de testes são instalados separadamente no ambiente de desenvolvimento.

A CLI lê até 65.537 bytes para aplicar o teto efetivo de 65.536 bytes antes de carregar JSON. Exige UTF-8 sem BOM, chaves únicas e números JSON finitos. Fontes de arquivo são verificadas por `fstat` e precisam ser arquivos regulares; stdin só é usado com `-` explícito. Stdin continua dependendo de um produtor que entregue e encerre a entrada.

Os orçamentos limitam períodos, dias de enumeração e resultados. A validação de sincronização de `DTSTART` tem custo separado de até 366 dias, registrado em `validationDays`, inclusive com orçamento zero. Esses limites não são um deadline, um limite global de memória do processo ou um isolamento do sistema operacional. Serviços que aceitem entradas de terceiros devem estabelecer seus próprios limites de processo e de requisição.

Um relatório incompleto é um prefixo comprovado, não uma lista completa de todas as datas da janela. Consumidores devem verificar `complete`, `stopReason` e `verifiedThrough`. Aumentar o orçamento e executar de novo pode ampliar a cobertura; não se deve interpretar saída vazia incompleta como ausência de ocorrências.

## Arquivos de saída e privacidade

`--output NEW` usa arquivo temporário no diretório de destino, sincronização do conteúdo e publicação por link exclusivo. Se o destino já existir, a operação falha sem sobrescrevê-lo. A funcionalidade depende dos recursos e das permissões do sistema de arquivos; ela não oferece isolamento contra um administrador ou outro agente capaz de alterar o próprio sistema de arquivos. O diretório pai deve ser escolhido pelo usuário e já existir.

Erros operacionais da CLI são sanitizados para não reproduzir o JSON rejeitado, os argumentos crus ou caminhos absolutos. O relatório, por sua própria finalidade, contém datas, regra e exceções normalizadas, incluindo `RDATE` e `EXDATE`. **Relatórios não são anônimos.** Revise entradas, stdout, arquivos gerados e anexos antes de compartilhar ou registrar em logs.

Os exemplos e fixtures do repositório usam dados sintéticos. Uma comparação com o oráculo de desenvolvimento verifica casos declarados; não comprova conformidade integral iCalendar nem substitui a validação do consumidor para seu uso concreto.
