# Serviço de bancas acadêmicas

O `defense-service` gerencia a composição, a agenda, a realização, as avaliações e o resultado das bancas. A aplicação usa entidades Python e casos de uso independentes do Django. Os adapters implementam HTTP, JWT RS256, persistência PostgreSQL e publicação Kafka. A integração consulta a API do `thesis-service` com o token do solicitante e revalida a aprovação do orientador, o curso e os vínculos na criação e no agendamento. A consulta é realizada antes da transação local. O serviço mantém seu próprio banco e sua própria trilha de auditoria.

## Execução

A partir da raiz, siga a configuração de identidade e chave pública dos serviços existentes. Use a mesma audiência e o mesmo emissor em identidade, monografias e bancas, conforme o contrato atual do emissor. Configure a chave pública em `THESIS_JWT_PUBLIC_KEY_HOST_FILE`. A chave privada permanece no emissor. Crie o arquivo local ignorado `.env.defense.local` com valores próprios para `DEFENSE_SECRET_KEY` e `DEFENSE_DB_PASSWORD`. Preserve o arquivo para os próximos boots. Opcionalmente, defina `DEFENSE_API_PORT` (padrão 8003) e `DEFENSE_KAFKA_TOPIC` (padrão `defense.events.v1`).

Os comandos abaixo funcionam no PowerShell e no shell Linux:

```sh
docker compose --env-file .env --env-file .env.defense.local -f infrastructure/compose.yaml -f infrastructure/compose.jwt-file.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml -f infrastructure/compose.defense.yaml config --quiet
docker compose --env-file .env --env-file .env.defense.local -f infrastructure/compose.yaml -f infrastructure/compose.jwt-file.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml -f infrastructure/compose.defense.yaml build thesis-api identity-api defense-api
docker compose --env-file .env --env-file .env.defense.local -f infrastructure/compose.yaml -f infrastructure/compose.jwt-file.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml -f infrastructure/compose.defense.yaml up -d --wait identity-api defense-api defense-outbox-worker
```

O inicializador cria `defense_db` e `defense_user` se ausentes. O usuário é proprietário apenas do banco de bancas, sem privilégios de superusuário, criação de papéis ou bancos. O PostgreSQL já existente fornece a persistência. `defense-migrate` aplica migrations antes da API e do worker. `defense-topic` cria o tópico se ausente. A API Gunicorn escuta em `127.0.0.1:8003` no host e responde 401 à sondagem sem credencial. Consulte `docker compose ps -a` e `docker compose logs defense-api defense-outbox-worker` com os mesmos arquivos e parâmetros.

Para rodar diretamente, instale `python -m pip install -r requirements.txt`. Configure `DEFENSE_SECRET_KEY`, `DEFENSE_DB_NAME`, `DEFENSE_DB_USER`, `DEFENSE_DB_PASSWORD`, `DEFENSE_DB_HOST`, `DEFENSE_DB_PORT`, `DEFENSE_JWT_PUBLIC_KEY_FILE`, `DEFENSE_JWT_ISSUER`, `DEFENSE_JWT_AUDIENCE`, `DEFENSE_THESIS_API_URL`, `DEFENSE_KAFKA_BOOTSTRAP_SERVERS` e `DEFENSE_KAFKA_TOPIC`. No host os padrões de rede são PostgreSQL `127.0.0.1:5434`, monografias `127.0.0.1:8001` e Kafka `localhost:9092`. Use `python manage.py migrate` uma vez e execute `python manage.py run_outbox_worker` em outro processo.

## API

O prefixo é `/api/defenses/`. As rotas aceitam JSON e usam `Authorization: Bearer <access_token>`. A resposta externa usa somente a credencial temporária enviada no corpo.

| Método e sufixo | Corpo ou operação |
| --- | --- |
| `POST /` | Proposta com `{"thesis_id":"<uuid>"}`. Coordenador do curso ou orientador vinculado. |
| `GET /` | Listagem no escopo do ator. Filtros `thesis_id`, `status`, `page` e `page_size` (máximo 100). |
| `GET /{id}/` | Consulta da banca. O estudante vê sua própria banca. A coordenação vê as bancas do curso e o orientador vê as que orienta ou integra. |
| `GET /{id}/members/` | Lista de participantes para gestão e membros internos com acesso. |
| `POST /{id}/members/` | Convida com `{"kind":"internal","academic_id":"<uuid>"}` ou `{"kind":"external","name":"Nome","email":"visitante@example.org"}`. |
| `DELETE /{id}/members/{member_id}/` | Remove convite durante a composição. Permite substituir convites recusados ou expirados. |
| `POST /{id}/members/{member_id}/response/` | Membro interno identificado pelo próprio JWT envia `{"accept":true}` ou `false`. |
| `POST /{id}/members/{member_id}/external-response/` | Membro externo envia `{"accept":true,"token":"<token>"}` ou recusa com `accept=false`. |
| `POST /{id}/schedule/` | `starts_at` e `ends_at` em ISO 8601, com `venue` ou `meeting_url` HTTPS. |
| `POST /{id}/cancel/` e `POST /{id}/hold/` | Cancela ou registra realização. Ambos usam corpo vazio. |
| `POST /{id}/evaluations/` | `{"grade":"8.50","opinion":"Parecer","recommendation":"conditional"}`. |
| `GET /{id}/evaluations/` | Gestores da banca consultam todos os pareceres. Os demais avaliadores consultam o próprio. |
| `GET /{id}/result/` | Resultado fechado e média. Enquanto houver avaliações pendentes, retorna 409. |

Administradores não recebem acesso por seu papel. Ao convidar um externo, copie o token devolvido uma única vez e envie por canal privado verificado junto com os UUIDs da banca e do convite. Use TLS e mantenha o token fora de URLs, logs, tickets e ferramentas de coleta de corpo. O prazo é 48 horas, com armazenamento apenas do hash até o uso. O token só permite aceitar ou recusar o próprio convite. Membros externos participam como convidados e a avaliação nesta versão pertence aos membros internos confirmados.

O agendamento exige pelo menos um membro interno e a confirmação de todos os convidados. A duração é de 15 minutos a 8 horas. Horários sobrepostos são recusados para a mesma sala, link, participante, aluno ou orientador. A reserva é serializada no PostgreSQL. A realização é registrada após o término agendado. A escala de notas é de 0 a 10, com até duas casas decimais. Cada membro interno confirmado vota uma vez e o último voto fecha o resultado. A média arredondada abaixo de 7 ou qualquer recomendação `rejected` causa reprovação. Nos demais casos, `conditional` causa aprovação com ressalvas e o restante resulta em aprovação. Essa é a política adotada pelo projeto, sujeita a validação institucional.

A Outbox persiste `defense.scheduled`, `defense.cancelled`, `defense.evaluation_registered` e `defense.completed` com a auditoria na transação de negócio. Os envelopes versão 1 levam `event_id`, `event_type`, `occurred_at`, `aggregate_id` e `data`. Pareceres e credenciais ficam fora dos eventos. A publicação é pelo menos uma vez e conserva o ID em retentativas. O resultado fica no banco das bancas. A propagação à monografia e o envio de convites ou lembretes são integrações futuras.

## Testes

Em `services/defense-service`, execute:

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --keepdb
```

Use um PostgreSQL de desenvolvimento/teste e uma credencial separada com capacidade de criar o banco temporário. Para um smoke em Docker com contas de teste, emita os tokens no `identity-service`, escolha uma monografia sintética aprovada, crie a banca, convide um avaliador interno, confirme como convidado e agende. Confira `defense.scheduled` no tópico e a leitura da banca pelo estudante titular. A testagem automatizada também cobre conclusão e avaliações com horários controlados.
