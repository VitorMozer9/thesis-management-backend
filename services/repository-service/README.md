# Repositório público de monografias

O `repository-service` mantém o catálogo público, os PDFs finais e os termos de autorização. PostgreSQL guarda metadados, resultados confirmados, recibos de eventos, auditoria e a revisão do catálogo. A API Gunicorn e o consumidor Kafka usam a mesma imagem Linux e o volume persistente `repository_documents`. O consumidor monta esse volume para leitura.

## Fluxo de publicação

1. Coordenação ou administração do curso envia os metadados, o PDF final e o PDF do termo assinado. Em cada escrita o repositório valida o JWT RS256 do Identity e consulta `GET /api/theses/{uuid}/` no Thesis com o token do solicitante. Confere o UUID e o curso assinado. Para uma versão corrigida, exige o SHA-256 da versão acadêmica já aprovada pelo orientador. O administrador tem o mesmo limite de curso da coordenação.
2. A Outbox do Defense publica `defense.completed` v1 em `defense.events.v1`. O envelope contém `event_id`, `event_type`, `version`, `occurred_at`, `aggregate_id` e `data`. O consumidor confere `defense_id`, `thesis_id`, `course_id` e `result` e consulta `GET /internal/completed-defenses/{defense_id}/` no Defense. Essa leitura usa uma credencial exclusiva entre serviços e devolve somente os IDs, o resultado fechado e o ano UTC do início da defesa. Assim, uma avaliação registrada em janeiro também pode publicar corretamente uma defesa realizada em dezembro. Eventos v1 anteriores continuam válidos.
3. Ao receber documentos, metadados ou conclusão, o serviço bloqueia a linha da monografia e verifica todos os requisitos. A liberação exige resultado `approved` ou `approved_with_conditions`, título, autor, orientador, palavras-chave, termo e PDF final. Com ressalvas, o arquivo deve ser entregue como `corrected` e ter hash diferente do PDF do Thesis. A coordenação confere o conteúdo das correções. A reprovação mantém o registro privado.
4. A publicação e sua auditoria são gravadas na mesma transação. O recebimento do evento também participa dessa transação. O catálogo passa a exibir a monografia assim que a última condição for satisfeita, qualquer que seja a ordem de chegada. A data `published_at` distingue registros pendentes de publicados. A API fecha as alterações após a publicação.

O Thesis entrega metadados pela API e mantém o volume acadêmico privado. A versão para divulgação é enviada ao repositório. O serviço armazena o termo apresentado e a revisão humana cabe à instituição, inclusive a autenticidade jurídica da assinatura. O termo fica fora do catálogo e das rotas de download.

## API

O host local padrão é `http://127.0.0.1:8004`. Nas rotas abaixo, `{id}` é o UUID da monografia no Thesis.

| Método e rota | Acesso | Entrada ou saída |
| --- | --- | --- |
| `GET /api/repository/` | Público | `title`, `author`, `keywords`, `advisor`, `course_id`, `year`, `page`, `page_size`. Retorna `results` e `has_next`. |
| `GET /api/repository/{id}/` | Público | Metadados publicados, banca, resultado, SHA-256 e instante da publicação. |
| `GET /api/repository/{id}/pdf/` | Público | PDF final como anexo após verificação do hash. Uma monografia privada ou desconhecida retorna 404. |
| `PUT /api/repository/admin/{id}/metadata/` | Coordenação ou administração do curso | JSON com `title`, `author`, `advisor` e lista `keywords`. O campo opcional `reported_year` permite conferir o ano da ficha catalográfica. Uma divergência com a banca bloqueia a liberação até a correção dos metadados. |
| `POST /api/repository/admin/{id}/documents/` | Coordenação ou administração do curso | Multipart com `file`, `sha256` hexadecimal minúsculo e `kind` igual a `authorization`, `final` ou `corrected`. |

As escritas devolvem `{"state":"pending"}` ou `{"state":"published"}`. Credencial inválida retorna 401, escopo insuficiente retorna 403 e uma alteração incompatível com a publicação retorna 409. Uma dependência indisponível pode causar 503. Campos desconhecidos são rejeitados. Use apenas nomes e palavras-chave autorizados para divulgação pública.

Exemplos em shell, com token de curta duração e UUID fornecidos pelo operador:

```sh
base=http://127.0.0.1:8004/api/repository
curl -X PUT "$base/admin/$THESIS_ID/metadata/" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Sistemas distribuídos","author":"Ana Silva","advisor":"Maria Costa","keywords":["consenso","redes"]}'
curl "$base/admin/$THESIS_ID/documents/" -H "Authorization: Bearer $TOKEN" \
  -F kind=authorization -F "sha256=$(sha256sum termo.pdf | cut -d' ' -f1)" -F file=@termo.pdf
curl "$base/admin/$THESIS_ID/documents/" -H "Authorization: Bearer $TOKEN" \
  -F kind=final -F "sha256=$(sha256sum final.pdf | cut -d' ' -f1)" -F file=@final.pdf
curl "$base/?author=Silva&keywords=redes&page_size=10"
```

## Pesquisa, integridade e recuperação

A busca por título, autor e palavras-chave usa termos completos com `tsvector` e índices GIN parciais do PostgreSQL. Os filtros são cumulativos. O orientador usa o nome público exato e o curso usa UUID. O banco filtra registros publicados antes de ordenar por data decrescente e UUID. O tamanho padrão da página é 20 e o máximo é 100.

Redis guarda somente resultados públicos serializados em JSON. A chave inclui a consulta normalizada e a revisão persistida do catálogo. Cada publicação altera essa revisão na transação, inclusive sob concorrência. Chaves antigas expiram pelo TTL. Uma falha de cache permite consultar diretamente o PostgreSQL.

Os documentos têm limite individual de 20 MiB. O serviço verifica os marcadores de início e fim do PDF, calcula SHA-256 durante a gravação e confere o digest esperado. O caminho deriva do UUID e do hash. A escrita temporária e a troca atômica ocorrem dentro do volume próprio. A integridade de ambos os documentos é conferida antes da liberação e a do PDF em cada download. Os backups devem manter banco e volume em conjunto. Rollback ou substituição de um documento pendente podem deixar arquivos privados sem referência. A limpeza requer reconciliação com o banco e backup. A aplicação não executa remoção automática.

O grupo Kafka usa confirmação manual após persistência. O recibo com ID e digest do envelope torna a reapresentação idempotente. Mensagens inválidas ou inconsistentes ficam na tabela `repository_invalidmessage` com tópico, partição, offset e motivo. Os demais tipos de evento são ignorados. Falha de banco, volume, credencial ou comunicação com o Defense interrompe o worker antes da confirmação. O Compose limita as reinicializações a três. Após corrigir a dependência, reinicie `repository-worker`. Para investigar quarentena, recupere a mensagem original pela coordenada no broker dentro do prazo de retenção. Após corrigir a origem ou a compatibilidade, reapresente o evento legítimo com o mesmo ID. A auditoria registra a conta JWT nas ações administrativas e o ID do evento nas liberações disparadas pelo consumidor.

## Docker e configuração

Parta da infraestrutura de desenvolvimento do projeto com `.env`, `.env.defense.local` e a chave pública já preparada. Na raiz do repositório, crie uma única vez o arquivo local ignorado de credenciais. O modo de criação exclusiva preserva um arquivo existente.

```sh
python -c "from pathlib import Path; from secrets import token_urlsafe; Path('.env.repository.local').open('x').writelines(k+'='+token_urlsafe(48)+'\n' for k in ('REPOSITORY_SECRET_KEY','REPOSITORY_DB_PASSWORD','REPOSITORY_VERIFICATION_KEY'))"
```

Os comandos seguintes funcionam em PowerShell e Linux. Em uma instalação nova, construa também as imagens locais do Thesis e do Identity pelo procedimento desses serviços.

```sh
docker compose --env-file .env --env-file .env.defense.local --env-file .env.repository.local -f infrastructure/compose.yaml -f infrastructure/compose.jwt-file.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml -f infrastructure/compose.defense.yaml -f infrastructure/compose.repository.yaml config --quiet
docker compose --env-file .env --env-file .env.defense.local --env-file .env.repository.local -f infrastructure/compose.yaml -f infrastructure/compose.jwt-file.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml -f infrastructure/compose.defense.yaml -f infrastructure/compose.repository.yaml build repository-api defense-api
docker compose --env-file .env --env-file .env.defense.local --env-file .env.repository.local -f infrastructure/compose.yaml -f infrastructure/compose.jwt-file.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml -f infrastructure/compose.defense.yaml -f infrastructure/compose.repository.yaml up -d --wait identity-api thesis-api defense-api defense-outbox-worker repository-api repository-worker
```

O inicializador cria `repository_db` e `repository_user` na instância PostgreSQL existente. O processo `repository-migrate` aplica as migrations antes da API e do consumidor. Use o mesmo prefixo Compose com `logs repository-worker`, `ps` ou `stop repository-api repository-worker`. O encerramento preserva o volume.

| Configuração | Uso |
| --- | --- |
| `REPOSITORY_SECRET_KEY`, `REPOSITORY_DB_PASSWORD` | Segredos exclusivos do Django e do papel PostgreSQL. |
| `REPOSITORY_DB_NAME/USER/HOST/PORT` | Variáveis com prefixo `REPOSITORY_DB_`. Padrões locais `repository_db`, `repository_user`, `127.0.0.1`, `5434`. |
| `REPOSITORY_JWT_PUBLIC_KEY_FILE`, `REPOSITORY_JWT_ISSUER`, `REPOSITORY_JWT_AUDIENCE` | PEM RSA de pelo menos 2048 bits e valores confiáveis do emissor. O Compose reaproveita a chave pública e o emissor/audiência do Identity. O consumidor de JWT exige `typ=at+jwt`, RS256, `iat`, `exp`, `sub`, `academic_id`, `role` e `course_id`. |
| `REPOSITORY_VERIFICATION_KEY` | Credencial aleatória de pelo menos 32 bytes entre o worker e a API Defense. Distribua e rotacione nos dois processos. A API pública do repositório dispensa essa credencial. |
| `REPOSITORY_THESIS_API_URL`, `REPOSITORY_DEFENSE_API_URL` | Bases HTTP confiáveis dos serviços. No host usam as portas 8001 e 8003. |
| `REPOSITORY_KAFKA_BOOTSTRAP_SERVERS`, `REPOSITORY_KAFKA_TOPIC`, `REPOSITORY_KAFKA_GROUP` | Padrões no host `localhost:9092`, `defense.events.v1` e `repository-publication-v1`. Compose usa o listener interno e acompanha `DEFENSE_KAFKA_TOPIC`. |
| `REPOSITORY_REDIS_URL`, `REPOSITORY_CACHE_TTL` | Banco Redis lógico 2 e TTL em segundos, padrão 120. |
| `REPOSITORY_MEDIA_ROOT`, `REPOSITORY_ALLOWED_HOSTS`, `REPOSITORY_API_PORT` | Diretório privado de documentos, hosts permitidos e porta publicada localmente, padrão 8004. |

O Compose destina-se ao desenvolvimento em rede confiável. Para exposição pública, configure TLS para as APIs e a comunicação entre serviços, gestão de segredos, controle de acesso ao broker, backup dos documentos e limites de corpo no proxy. Restrinja a rota interna de bancas à rede do worker.

## Execução local e testes

Em `services/repository-service`, use Python 3.14 e configure as variáveis indicadas. A API e o worker são processos independentes.

```sh
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py run_repository_worker
```

No Linux, inicie a API com `gunicorn --bind 127.0.0.1:8004 config.wsgi:application`. Para a suíte, forneça uma credencial PostgreSQL de teste com permissão para criar o banco temporário, separada do papel de execução. A suíte verifica a pesquisa no PostgreSQL, a publicação nas duas ordens de chegada, a autorização, a integridade e as falhas transacionais. Para um smoke entre serviços, use dados sintéticos, agende e realize a banca pelo Defense, entregue os dois documentos e confira a pesquisa e o hash do download após o fechamento da última avaliação.
