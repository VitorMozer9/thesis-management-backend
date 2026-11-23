# Serviço de monografias

O `thesis-service` gerencia rascunhos, PDFs, submissões e decisões dos orientadores. A API usa Django REST Framework e aceita tokens de acesso emitidos por uma autoridade externa. As decisões acadêmicas e o histórico de operações ficam no PostgreSQL.

## Componentes

| Caminho | Responsabilidade |
| --- | --- |
| `thesis/domain` | Entidade imutável, estados, regras de transição e eventos. |
| `thesis/application` | Casos de uso, identidade acadêmica e portas para persistência, transações, bloqueios, arquivos, auditoria e publicação. |
| `thesis/adapters` | API REST, autenticação JWT, ORM Django, armazenamento local, Redis e produtor Kafka. |
| `config` | Configuração Django, rotas e composição de dependências. |
| `thesis/management/commands` | Publicação dos eventos pendentes e execução contínua do worker da Outbox. |

## Ambiente local

Use Python 3.14. A infraestrutura de desenvolvimento em `../../infrastructure/compose.yaml` publica PostgreSQL 18 em `127.0.0.1:5434`, Redis 7.4 em `127.0.0.1:6379` e Kafka 4.4 em `127.0.0.1:9092`. A API e o worker são processos separados.

O serviço lê variáveis de ambiente e carrega o arquivo `.env` da raiz do repositório. Preencha as credenciais com valores próprios do ambiente. Use o mesmo banco, tópico e configuração de conexão para API e worker.

| Variáveis | Uso |
| --- | --- |
| `DJANGO_SECRET_KEY`, `DJANGO_DEBUG` | Chave obrigatória do Django e depuração opcional, desativada por padrão. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Nome do banco e credenciais obrigatórios. |
| `DB_HOST`, `DB_PORT` | Host e porta do PostgreSQL. Padrões locais `127.0.0.1` e `5434`. |
| `REDIS_URL` | Conexão para locks e estado do upload. Padrão `redis://127.0.0.1:6379/0`. |
| `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_THESIS_EVENTS_TOPIC` | Endereço inicial do broker e tópico. Padrões `localhost:9092` e `thesis.events.v1`. |
| `THESIS_JWT_PUBLIC_KEY`, `THESIS_JWT_ISSUER`, `THESIS_JWT_AUDIENCE` | Chave pública, emissor e público-alvo exigidos para aceitar tokens. |

A partir de `services/thesis-service`, crie e ative um ambiente virtual. Exemplo em PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
docker compose --env-file ../../.env -f ../../infrastructure/compose.yaml up -d
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Em outro terminal, com o ambiente ativado, execute `python manage.py run_outbox_worker`. O worker processa até 20 eventos por ciclo e usa intervalo padrão de 5 segundos. As opções `--interval` e `--limit` ajustam esses valores. Para executar um ciclo, use `--once`.

## API

Envie `Authorization: Bearer <token>` em todas as requisições. O contrato descreve como o futuro serviço de identidade deve verificar e assinar o vínculo acadêmico e o curso. [Contrato de identidade e permissões](IDENTITY.md)

| Método e rota | Entrada ou resultado |
| --- | --- |
| `POST /api/theses/` | Cria rascunho com `title`, `student_id`, `course_id` e `abstract` opcional. |
| `GET /api/theses/` | Lista paginada. Filtra por aluno, orientador, curso e estado. `search` busca em título e palavras-chave. `page_size` tem padrão 20 e máximo 100. |
| `GET /api/theses/{id}/` | Retorna os dados da monografia visível ao ator. |
| `PATCH /api/theses/{id}/` | Atualiza título, resumo ou palavras-chave. A coordenação pode associar um orientador elegível em uma requisição exclusiva para esse campo. |
| `POST /api/theses/{id}/pdf/` | Envie `file` em multipart. O serviço valida extensão, assinatura inicial de PDF e limite de 20 MiB e calcula o SHA-256. |
| `GET /api/theses/{id}/upload-status/` | Consulta o estado temporário registrado no Redis. |
| `POST /api/theses/{id}/submit/` | Submete o rascunho completo. |
| `POST /api/theses/{id}/approve/` e `POST /api/theses/{id}/reject/` | Orientador decide sobre uma submissão. Envie o corpo vazio. |
| `DELETE /api/theses/{id}/` | Exclui um rascunho próprio e preserva arquivo e histórico. |

## Transações, auditoria e arquivos

Cada criação, edição de metadados, associação de orientador, upload, submissão, aprovação, rejeição ou exclusão confirmada insere uma linha em `thesis_audit`. A linha contém um UUID próprio, UUID da conta, UUID acadêmico, papel, ação, UUID da monografia e instante em UTC. O vínculo com a monografia usa seu UUID sem exclusão em cascata. A API de auditoria interna oferece apenas inserção. Não há rota HTTP de auditoria.

O caso de uso exige uma identidade acadêmica verificada mesmo quando chamado diretamente. A auditoria registra sucessos na mesma transação PostgreSQL da escrita de negócio e, nas operações que geram eventos, da Outbox. Um erro na auditoria desfaz essas escritas. Requisições negadas e transações revertidas não geram linha de sucesso. O registro contém somente identificadores e dados da operação, sem cópia do token, dos metadados textuais ou do PDF.

Os PDFs ficam sob `media/` no diretório do serviço. O upload grava um novo arquivo antes de atualizar sua referência e a auditoria no PostgreSQL. Se essa etapa falhar, tenta remover o novo arquivo. O Redis acompanha o processamento separadamente. Uma interrupção entre etapas, uma falha de limpeza ou o rollback posterior de uma transação externa pode deixar arquivo órfão ou estado temporário divergente. A substituição e a exclusão preservam arquivos anteriores. A retenção e a reconciliação do armazenamento ainda dependem de política operacional.

A Outbox publica `thesis.created`, `thesis.submitted`, `thesis.advisor_approved` e `thesis.advisor_rejected`. Se o Kafka estiver indisponível, o evento continua pendente. A entrega é pelo menos uma vez e o identificador do evento é preservado nas retentativas. Os consumidores devem tratar duplicatas.

## Verificação

Execute os comandos abaixo no diretório do serviço, com PostgreSQL e Redis disponíveis. O usuário PostgreSQL precisa poder criar o banco temporário de testes. Os testes HTTP usam um emissor de teste com chaves geradas durante a execução. Os testes de publicação simulam o produtor Kafka.

```console
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```
