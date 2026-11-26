# Zenit WhatsApp — piloto de histórico adicional
Código isolado na branch zenit-whatsapp-history-pilot. Base Evolution API 2.3.7 (cd800f2976e1e5b682fbf86a01ee4d85ae61f370).

## O que implementa
- Solicitação de histórico pelo protocolo Baileys, sem enviar mensagens aos contatos.
- Ativação explícita por instância, após conexão e período de silêncio da sincronização inicial.
- Busca em lotes de 50, por padrão 5 conversas e 2 solicitações por conversa por rodada.
- Conversas individuais apenas; lista opcional de JIDs para piloto controlado.
- Usa a mensagem mais antiga armazenada como âncora e só avança quando o banco registra uma mensagem estritamente mais antiga.
- Checkpoints em tabela própria ZenitHistoryCheckpoint; não migra nem exclui tabelas existentes.
- Intervalos, pausa por ausência de avanço, reconsulta após reconexão e deduplicação no importador de histórico.
- Remove o comando textual de depuração onDemandHistSync e o dump bruto das respostas de histórico sob demanda.

## Configuração piloto
No serviço Docker de teste, configure as variáveis habituais da Evolution, inclusive PostgreSQL, DATABASE_SAVE_DATA_HISTORIC=true e chave de autenticação. Acrescente:
```ini
ZENIT_HISTORY_ENABLED=true
ZENIT_HISTORY_INSTANCES=Zenit teste 2
ZENIT_HISTORY_MAX_CHATS=5
ZENIT_HISTORY_MAX_BATCHES=2
ZENIT_HISTORY_QUIET_SECONDS=120
ZENIT_HISTORY_INTERVAL_SECONDS=300
ZENIT_HISTORY_WAIT_SECONDS=45
ZENIT_HISTORY_NO_PROGRESS_MINUTES=1440
```
Opcional: ZENIT_HISTORY_JIDS=JID1,JID2 (somente JIDs individuais autorizados). Sem essa variável, percorre os chats individuais existentes na instância explicitamente autorizada. Não coloque identificadores, tokens ou credenciais no GitHub.

## Deploy e aceitação
O Dockerfile usa a imagem 2.3.7 e o código-fonte da revisão acima. Contexto de build: evolution-history. No Render, use a branch do piloto com Dockerfile evolution-history/Dockerfile e contexto evolution-history. Não rode duas Evolution usando as mesmas sessões de WhatsApp ou o mesmo banco simultaneamente. Teste primeiro em ambiente separado, com dados de teste autorizados. Não faça deploy na instalação atual sem backup e plano de rollback.
Confira os logs [zenit-history] round e compare quantidade e data mais antiga por chat. Uma resposta do WhatsApp sem mensagem mais antiga não comprova recuperação. A lógica não promete histórico integral nem garante metadados de anúncios. A deduplicação adicional é limitada à importação de histórico, não corrige todos os duplicados do sistema. A tabela de checkpoint não impede múltiplos workers em serviços diferentes; apenas uma instância de serviço deve processar o mesmo banco.
O Render gratuito pode suspender o processo e o PostgreSQL gratuito expira. O piloto não equivale a produção 24h.
## Validação
O patch exige âncoras exatas no código original e falha se forem diferentes. A compilação completa e o teste em uma instância real são etapas obrigatórias antes de considerar o piloto aprovado. Desative com ZENIT_HISTORY_ENABLED=false.
