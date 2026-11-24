# Serviço de notificações

O serviço recebe eventos Kafka, persiste o recebimento em PostgreSQL e confirma o offset. Um processo separado resolve destinatários, cria notificações e envia e-mails em português por SMTP. Os e-mails levam assunto e referência do recurso. A API oferece somente consulta autenticada.

| Evento v1 | Tópico padrão | Destinatários |
| --- | --- | --- |
| `thesis.submitted` | `thesis.events.v1` | Orientador vinculado |
| `defense.scheduled` | `defense.events.v1` | Estudante, orientador e membros confirmados |
| `defense.cancelled` | `defense.events.v1` | Estudante, orientador e convidados que não recusaram |
| `repository.published` | `repository.events.v1` | Autor da monografia |

As rotas internas do Thesis, Defense e Repository conferem o UUID do evento na Outbox de origem. O Thesis também fornece o UUID do autor da publicação. O Identity resolve UUIDs acadêmicos para IDs de conta e e-mails ativos. Para membros externos, a banca fornece o e-mail registrado no convite. Cada fonte recebe uma credencial de máquina distinta, usada somente pelo processo de entrega. Em produção, use TLS na rede entre serviços, restrinja as rotas internas no proxy e proteja o acesso ao broker. A Outbox do Repository começa a registrar eventos a partir da instalação da migration, sem republicar o catálogo anterior.

## Execução Docker

Na raiz, prepare os arquivos de ambiente dos serviços existentes. Gere uma vez o arquivo local ignorado para notificações.

```sh
python -c "from pathlib import Path; from secrets import token_urlsafe; Path('.env.notification.local').open('x').writelines(k+'='+token_urlsafe(48)+'\n' for k in ('NOTIFICATION_SECRET_KEY','NOTIFICATION_DB_PASSWORD','NOTIFICATION_THESIS_KEY','NOTIFICATION_IDENTITY_KEY','NOTIFICATION_DEFENSE_KEY','NOTIFICATION_REPOSITORY_KEY'))"
docker compose --env-file .env --env-file .env.defense.local --env-file .env.repository.local --env-file .env.notification.local -f infrastructure/compose.yaml -f infrastructure/compose.jwt-file.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml -f infrastructure/compose.defense.yaml -f infrastructure/compose.repository.yaml -f infrastructure/compose.notification.yaml config --quiet
docker compose --env-file .env --env-file .env.defense.local --env-file .env.repository.local --env-file .env.notification.local -f infrastructure/compose.yaml -f infrastructure/compose.jwt-file.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml -f infrastructure/compose.defense.yaml -f infrastructure/compose.repository.yaml -f infrastructure/compose.notification.yaml build thesis-api identity-api defense-api repository-api notification-api
docker compose --env-file .env --env-file .env.defense.local --env-file .env.repository.local --env-file .env.notification.local -f infrastructure/compose.yaml -f infrastructure/compose.jwt-file.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml -f infrastructure/compose.defense.yaml -f infrastructure/compose.repository.yaml -f infrastructure/compose.notification.yaml up -d --wait identity-api thesis-api thesis-outbox-worker defense-api defense-outbox-worker repository-api repository-worker repository-publication-outbox notification-api notification-kafka notification-delivery
```

O Compose cria `notification_db` com um papel limitado, executa migrations em um único processo e mantém os volumes existentes. Abra o Mailpit em `http://127.0.0.1:8025`. Para testar, espere o grupo Kafka se inicializar, submeta uma monografia sintética com orientador vinculado e procure o assunto “Monografia submetida”. A API escuta em `127.0.0.1:8005`.

| Configuração | Uso |
| --- | --- |
| `NOTIFICATION_DB_NAME`, `NOTIFICATION_DB_USER`, `NOTIFICATION_DB_PASSWORD`, `NOTIFICATION_DB_HOST`, `NOTIFICATION_DB_PORT` | PostgreSQL. Padrão local `notification_db`, `notification_user`, `127.0.0.1:5434`. |
| `NOTIFICATION_SECRET_KEY`, `NOTIFICATION_ALLOWED_HOSTS`, `NOTIFICATION_API_PORT` | Django e porta local. |
| `NOTIFICATION_JWT_PUBLIC_KEY_FILE`, `NOTIFICATION_JWT_ISSUER`, `NOTIFICATION_JWT_AUDIENCE` | Contrato RS256 do Identity. Compose usa a chave pública montada e a audiência e o emissor do Identity. |
| `NOTIFICATION_THESIS_URL`, `NOTIFICATION_IDENTITY_URL`, `NOTIFICATION_DEFENSE_URL`, `NOTIFICATION_REPOSITORY_URL` | Bases HTTP. No host, portas 8001 a 8004. |
| `NOTIFICATION_THESIS_KEY`, `NOTIFICATION_IDENTITY_KEY`, `NOTIFICATION_DEFENSE_KEY`, `NOTIFICATION_REPOSITORY_KEY` | Chaves do worker. Na fonte correspondente configure `NOTIFICATION_LOOKUP_KEY` com o mesmo valor. |
| `NOTIFICATION_KAFKA_BOOTSTRAP_SERVERS`, `NOTIFICATION_KAFKA_GROUP`, `NOTIFICATION_KAFKA_OFFSET_RESET` | Padrões `localhost:9092`, `notification-delivery-v1` e `latest`. Use `earliest` com um grupo novo somente para reprocessamento histórico intencional. |
| `KAFKA_THESIS_EVENTS_TOPIC`, `DEFENSE_KAFKA_TOPIC`, `REPOSITORY_PUBLICATION_TOPIC` | Tópicos da tabela. |
| `NOTIFICATION_SMTP_HOST`, `NOTIFICATION_SMTP_PORT`, `NOTIFICATION_SMTP_USER`, `NOTIFICATION_SMTP_PASSWORD`, `NOTIFICATION_SMTP_TLS` | Servidor SMTP. O Compose usa `mailpit:1025` por padrão. Use `true` para STARTTLS. |
| `NOTIFICATION_FROM_EMAIL`, `NOTIFICATION_SMTP_TIMEOUT`, `NOTIFICATION_MAX_ATTEMPTS` | Remetente, timeout padrão de 10 segundos e até oito tentativas. |

## Consulta e recuperação

Envie `Authorization: Bearer <access_token>` para `GET /api/notifications/` ou `GET /api/notifications/{uuid}/`. A lista retorna até 100 notificações recentes vinculadas à conta e ao UUID acadêmico autenticados. O detalhe devolve 404 fora desse escopo. Convites externos são atendidos por e-mail.

O consumidor registra envelopes inválidos em `notifications_invalidmessage` com a coordenada Kafka e um código. Falhas de banco deixam o offset disponível para reprocessamento. Falhas de consulta ou entrega ficam registradas em `notifications_incomingevent` ou `notifications_notification`, com retentativas exponenciais para falhas transitórias. E-mails indisponíveis nunca recebem status de envio. Após corrigir a origem de uma falha definitivamente encerrada, um operador pode reativar o registro afetado no banco, ajustando `status`, `attempts` e `next_attempt`, depois de verificar o histórico de entrega. Preserve a chave idempotente.

A chave por evento e destinatário lógico impede novas filas para o mesmo par. Bloqueios no banco evitam que workers concorrentes enviem a mesma linha e o `Message-ID` permanece estável. SMTP e PostgreSQL são sistemas independentes. Uma interrupção após a aceitação SMTP e antes do commit pode resultar em novo envio.

Para executar fora do Docker, instale `requirements.txt` com Python 3.14 e rode em `services/notification-service`:

```sh
python manage.py migrate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py run_notification_worker kafka
python manage.py run_notification_worker delivery
```

Execute os dois últimos comandos em processos distintos. Para testes, forneça uma credencial PostgreSQL com permissão de criar banco de teste.
