# Serviço de monografias

O `thesis-service` gerencia rascunhos, PDFs, submissões e decisões dos orientadores. A API usa Django REST Framework e aceita tokens de acesso emitidos por uma autoridade externa. As decisões acadêmicas e o histórico de operações ficam no PostgreSQL.

## Componentes

| Caminho | Responsabilidade |
| --- | --- |
| `thesis/domain` | Entidade imutável, estados, regras de transição e eventos. |
| `thesis/application` | Casos de uso, identidade acadêmica e portas para persistência, transações, bloqueios, arquivos, auditoria e publicação. |
| `thesis/adapters` | API REST, autenticação JWT, ORM Django, armazenamento local, Redis, produtor e consumidor Kafka e extrator de texto. |
| `config` | Configuração Django, rotas e composição de dependências. |
| `thesis/management/commands` | Comandos independentes para publicar a Outbox e processar os PDFs. |

## Execução integral em contêineres Linux

Execute os comandos desta seção **na raiz do repositório**. Use Docker Desktop em modo Linux no Windows ou Docker Engine com Compose v2 no Linux. Conserve o projeto Compose existente (`infrastructure` por padrão). Alterar o nome do projeto faz o Compose procurar volumes diferentes. Para uma instalação nova, crie o arquivo de ambiente apenas se ainda não existir.

PowerShell:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Linux:

```sh
test -e .env || (umask 077 && cp .env.example .env)
```

Preencha no `.env` as credenciais do PostgreSQL e a chave do Django. Em um banco já inicializado, use as credenciais correspondentes ao volume existente. O Compose fornece os endereços internos `postgres:5432`, `redis:6379` e `kafka:19092`. O listener Kafka do host permanece em `localhost:9092`. A API publica somente em `127.0.0.1:8001` por padrão, configurável com `THESIS_API_PORT`. O Gunicorn escuta em 8000 dentro do contêiner e o Compose fixa `DEBUG=False`. Inclua o hostname da requisição em `DJANGO_ALLOWED_HOSTS` e mantenha `127.0.0.1` para a verificação de saúde. `THESIS_RATE_WINDOW_SECONDS`, `THESIS_UPLOAD_LIMIT` e `THESIS_SUBMIT_LIMIT` são repassados à API e aos workers, com padrões `60`, `10` e `5`. Todas as réplicas da API compartilham as cotas pelo Redis do Compose.

Para aceitar tokens, preencha emissor e público-alvo conforme [o contrato JWT](IDENTITY.md). A configuração base aceita `THESIS_JWT_PUBLIC_KEY` em PEM. Para montar um arquivo externo somente para leitura, defina `THESIS_JWT_PUBLIC_KEY_HOST_FILE` como caminho absoluto do PEM público (no Windows, por exemplo, `C:/chaves/identity-public.pem`). Acrescente `-f infrastructure/compose.jwt-file.yaml` **depois** do arquivo Compose principal em todos os comandos relativos à pilha. O arquivo prevalece sobre o PEM do ambiente e precisa estar legível pelo UID 10001. A chave privada fica no emissor. Sem configuração de confiança, as rotas protegidas recusam acesso.

No ambiente local integrado, o emissor é o `identity-service` (`THESIS_JWT_ISSUER=urn:tcc:identity`, `THESIS_JWT_AUDIENCE=urn:tcc:api`) e a chave pública vem de `export_jwt_public_key`. A inicialização conjunta, os usuários de desenvolvimento e o teste ponta a ponta estão descritos no [guia de infraestrutura](../../infrastructure/README.md).

### Build, inicialização e verificação

Os comandos a seguir são iguais no PowerShell e no shell Linux:

```sh
docker compose --env-file .env -f infrastructure/compose.yaml config --quiet
docker compose --env-file .env -f infrastructure/compose.yaml build thesis-api
docker compose --env-file .env -f infrastructure/compose.yaml up -d --wait
docker compose --env-file .env -f infrastructure/compose.yaml ps -a
docker compose --env-file .env -f infrastructure/compose.yaml exec thesis-api python manage.py showmigrations thesis
docker compose --env-file .env -f infrastructure/compose.yaml logs --tail 50 thesis-api thesis-outbox-worker thesis-pdf-worker
```

`thesis-migrate` executa `python manage.py migrate --noinput` após o PostgreSQL ficar saudável. A API e os dois workers aguardam seu sucesso. Para repetir uma migração manualmente em janela de manutenção, use `docker compose --env-file .env -f infrastructure/compose.yaml run --rm thesis-migrate`. `thesis-topic` usa o listener interno para criar o tópico configurado se ele ainda não existir. A saída com código zero dos dois serviços de inicialização é esperada.

API e workers usam a mesma imagem e o usuário 10001. A API é considerada saudável quando a rota protegida responde 401 à sondagem sem token. O teste ponta a ponta abaixo verifica também a cadeia de dependências. Os workers têm até três tentativas automáticas de reinício por falha. Após corrigir a causa indicada nos logs, use `docker compose --env-file .env -f infrastructure/compose.yaml restart thesis-pdf-worker` ou o nome do worker da Outbox.

### Testes e persistência

```sh
docker compose --env-file .env -f infrastructure/compose.yaml exec thesis-api python manage.py check
docker compose --env-file .env -f infrastructure/compose.yaml run --rm --no-deps -e MEDIA_ROOT=/tmp/test-media -e REDIS_URL=redis://redis:6379/15 thesis-api python manage.py test --keepdb
docker compose --env-file .env -f infrastructure/compose.yaml run --rm --no-deps thesis-api python -m thesis.tests.compose_smoke
```

O último comando usa uma instância temporária de Gunicorn, acessível apenas dentro do contêiner de teste. Ela verifica JWTs RS256 com uma chave pública temporária. O teste cria um rascunho sintético no banco configurado, associa o orientador, envia um PDF textual, submete e verifica texto e SHA-256 após os workers reais processarem o evento. O UUID impresso permite conferir a linha após reiniciar ou recriar API e workers. O PDF, a linha, a auditoria e os eventos sintéticos permanecem gravados.

O volume `thesis_media` é montado em `/var/lib/thesis/media`, com escrita na API e somente leitura no worker de PDF. A imagem prepara o diretório com UID/GID 10001 para a inicialização de um volume novo. Os volumes existentes continuam nos caminhos anteriores: PostgreSQL 18 usa `postgres18_data:/var/lib/postgresql`, Redis usa `redis_data:/data` e Kafka usa `kafka_data:/tmp/kraft-combined-logs`. A declaração legada `postgres_data` também é mantida. Preserve o ID KRaft e o acesso de escrita do usuário do Kafka ao volume inicializado.

**Acervo anterior do Windows.** O volume novo começa vazio. Antes de liberar o consumidor para processar submissões que apontem ao acervo local, mantenha a API e o worker de PDF parados e faça backup do diretório `services/thesis-service/media`, do banco e do volume de destino. Monte a origem somente para leitura em um contêiner auxiliar. Compare as chaves relativas e o SHA-256 de cada arquivo com o banco e com arquivos já presentes no volume. Copie apenas arquivos ausentes, preservando os caminhos e recusando colisões de conteúdo. Faça a cópia como UID 10001, confira contagens e hashes na origem e no destino e teste a leitura pelo worker antes de retomar. Conserve a origem para recuperação. A inicialização Compose não executa essa cópia.

Para encerrar a pilha e conservar os volumes:

```sh
docker compose --env-file .env -f infrastructure/compose.yaml stop
```

A configuração atende desenvolvimento e validação em host local. Uma exposição pública requer terminação TLS, gestão de segredos e de backups, controle de rede, revisão dos listeners sem criptografia e política de retenção para dados acadêmicos.

## Ambiente local

Use Python 3.14. A infraestrutura de desenvolvimento em `../../infrastructure/compose.yaml` publica PostgreSQL 18 em `127.0.0.1:5434`, Redis 7.4 em `127.0.0.1:6379` e Kafka 4.4 em `127.0.0.1:9092`. API, publicador da Outbox e consumidor de PDFs são processos separados.

O serviço lê variáveis de ambiente e carrega o arquivo `.env` da raiz do repositório. Preencha as credenciais com valores próprios do ambiente. Use o mesmo banco, tópico e configuração de conexão para API e worker.

| Variáveis | Uso |
| --- | --- |
| `DJANGO_SECRET_KEY`, `DJANGO_DEBUG` | Chave obrigatória do Django e depuração opcional, desativada por padrão. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Nome do banco e credenciais obrigatórios. |
| `DB_HOST`, `DB_PORT` | Host e porta do PostgreSQL. Padrões locais `127.0.0.1` e `5434`. |
| `REDIS_URL` | Conexão para locks, estado do upload e controle de taxa. Padrão `redis://127.0.0.1:6379/0`. |
| `THESIS_RATE_WINDOW_SECONDS`, `THESIS_UPLOAD_LIMIT`, `THESIS_SUBMIT_LIMIT` | Janela em segundos e cotas por conta para upload e submissão. Padrões `60`, `10` e `5`. Valores devem ser inteiros positivos. |
| `REDIS_TEST_URL` | Banco Redis isolado usado pelos testes de adapters Redis. Padrão `redis://127.0.0.1:6379/15`. |
| `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_THESIS_EVENTS_TOPIC` | Endereço inicial do broker e tópico. Padrões `localhost:9092` e `thesis.events.v1`. |
| `KAFKA_PDF_GROUP_ID` | Grupo exclusivo do consumidor de submissões. Padrão `thesis-pdf-extraction-v1`. |
| `THESIS_JWT_PUBLIC_KEY`, `THESIS_JWT_ISSUER`, `THESIS_JWT_AUDIENCE` | Chave pública, emissor e público-alvo exigidos para aceitar tokens. |

A partir de `services/thesis-service`, crie e ative um ambiente virtual. Exemplo em PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
docker compose --env-file ../../.env -f ../../infrastructure/compose.yaml up -d postgres redis kafka
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
| `POST /api/theses/{id}/pdf/` | Envie `file` em multipart. O serviço valida extensão, assinatura inicial de PDF e limite de 20 MiB e calcula o SHA-256. Sujeito a controle de taxa (429). |
| `GET /api/theses/{id}/upload-status/` | Consulta o estado temporário registrado no Redis. |
| `POST /api/theses/{id}/submit/` | Submete o rascunho completo. Sujeito a controle de taxa (429). |
| `POST /api/theses/{id}/approve/` e `POST /api/theses/{id}/reject/` | Orientador decide sobre uma submissão. Envie o corpo vazio. |
| `DELETE /api/theses/{id}/` | Exclui um rascunho próprio e preserva arquivo e histórico. |

## Transações, auditoria e arquivos

Cada criação, edição de metadados, associação de orientador, upload, submissão, aprovação, rejeição ou exclusão confirmada insere uma linha em `thesis_audit`. A linha contém um UUID próprio, UUID da conta, UUID acadêmico, papel, ação, UUID da monografia e instante em UTC. O vínculo com a monografia usa seu UUID sem exclusão em cascata. A API de auditoria interna oferece apenas inserção. Não há rota HTTP de auditoria.

O caso de uso exige uma identidade acadêmica verificada mesmo quando chamado diretamente. A auditoria registra sucessos na mesma transação PostgreSQL da escrita de negócio e, nas operações que geram eventos, da Outbox. Um erro na auditoria desfaz essas escritas. Requisições negadas e transações revertidas não geram linha de sucesso. O registro contém somente identificadores e dados da operação, sem cópia do token, dos metadados textuais ou do PDF.

Os PDFs ficam sob `media/` no diretório do serviço, na chave `theses/{thesis_id}/{uuid}.pdf`. O upload grava um novo arquivo antes de atualizar sua referência e a auditoria no PostgreSQL. Se essa etapa falhar, tenta remover o novo arquivo. O Redis acompanha o processamento separadamente. Uma interrupção entre etapas, uma falha de limpeza ou o rollback posterior de uma transação externa pode deixar arquivo órfão ou estado temporário divergente. A substituição e a exclusão preservam arquivos anteriores. A retenção e a reconciliação do armazenamento ainda dependem de política operacional.

### PDFs duplicados e integridade SHA-256

O SHA-256 é calculado em blocos de 1 MiB, junto com a verificação do limite de 20 MiB, antes de qualquer gravação. O arquivo atual do rascunho é reaproveitado somente quando todas as condições abaixo valem:

- o hash enviado é igual ao `file_sha256` registrado na própria monografia;
- a chave registrada pertence ao prefixo `theses/{thesis_id}/` da mesma monografia;
- o arquivo existe e o SHA-256 recalculado a partir dos bytes armazenados confere.

Nesse caso não há nova cópia, mas a referência é regravada com a verificação otimista de `update_draft` e a auditoria registra `pdf_uploaded`. Se o arquivo estiver ausente, ilegível ou com hash divergente, o serviço registra um aviso no log e grava uma nova cópia íntegra em outra chave. Conteúdo diferente sempre gera nova chave. Monografias diferentes nunca compartilham o mesmo arquivo físico, mesmo com conteúdo idêntico.

Uma falha do PostgreSQL desfaz a referência e a auditoria. Um arquivo reaproveitado nunca é removido nesse caso, e um arquivo novo é removido. Somente rascunhos aceitam upload. Monografias submetidas ou avaliadas não têm o arquivo substituído. O repositório filtra as monografias pelo ator, por isso o upload em rascunho alheio responde 404. Duas requisições simultâneas no mesmo rascunho são serializadas pelo lock Redis (a segunda recebe 409). Se o lock expirar, a condição `previous` de `update_draft` impede sobrescrita silenciosa.

## Controle de taxa

Upload de PDF e submissão têm cotas independentes por conta autenticada. A identidade é o claim `sub` do JWT RS256 verificado (`AcademicIdentity.account_id`). Campos do corpo da requisição não são considerados. O contador fica no Redis compartilhado, na chave `thesis:rate:{upload|submit}:{account_id}`, em janela fixa de `THESIS_RATE_WINDOW_SECONDS`.

O consumo é feito por um script Lua executado atomicamente no Redis: lê o contador, recusa quando a cota está esgotada e, caso contrário, incrementa e garante a expiração. Por isso vários processos Gunicorn e hosts compartilham a mesma cota sem condição de corrida. Requisições recusadas não incrementam o contador nem prolongam a janela. Uma chave sem expiração recebe uma nova expiração na próxima consulta.

A cota é consumida somente depois da autenticação, do papel, da autorização por recurso, do status, da extensão, do tamanho, da assinatura e do SHA-256 do PDF e, na submissão, das regras de domínio. Requisições sem token (401), inválidas (400), negadas (403/404) ou em conflito de lock (409) não gastam cota. Ao exceder a cota, a API responde 429 com o cabeçalho `Retry-After`. Na submissão, o consumo ocorre dentro da transação, de modo que 429 não altera estado, Outbox nem auditoria. Uma falha que ocorra depois do consumo, como erro de banco, mantém a unidade consumida.

Se o Redis estiver indisponível, upload e submissão falham de forma fechada com 503, sem gravar arquivo, referência, evento ou auditoria.

A Outbox publica `thesis.created`, `thesis.submitted`, `thesis.advisor_approved` e `thesis.advisor_rejected`. Se o Kafka estiver indisponível, o evento continua pendente. A entrega é pelo menos uma vez e o identificador do evento é preservado nas retentativas. Os consumidores devem tratar duplicatas.

## Extração assíncrona após a submissão

Ao submeter, a API grava a monografia, a auditoria, o evento da Outbox e uma linha `pending` em `thesis_pdf_extractions` na mesma transação. Essa linha associa o `event_id` ao UUID da monografia, à chave de armazenamento e ao SHA-256 naquele instante. O HTTP pode responder antes de o Kafka estar disponível. A extração ocorre em outro processo, que precisa acessar o mesmo banco e diretório `media/` usados pela API.

O publicador entrega o envelope existente no tópico `KAFKA_THESIS_EVENTS_TOPIC`. O consumidor reconhece `event_type=thesis.submitted`, versão inteira 1, `event_id` UUID, `occurred_at` com fuso horário e UUIDs iguais em `aggregate_id` e `data.thesis_id`. Outros tipos identificáveis são ignorados com confirmação do offset. Um grupo novo começa no primeiro offset ainda retido. Um grupo existente retoma da posição confirmada.

A linha passa a `processing`. O consumidor bloqueia essa linha, lê o PDF, confere o SHA-256 e executa o pypdf em um subprocesso. Antes de gravar o texto, verifica novamente a referência e o hash na monografia. A transação termina antes da confirmação síncrona do offset. Se essa confirmação falhar, a reentrega encontra o registro terminal e dispensa nova extração. Um registro `processing` após interrupção pode ser retomado. A exclusão da monografia remove o resultado associado.

| Estado | Interpretação |
| --- | --- |
| `pending` | Aguardando entrega. Confira a Outbox, os dois workers e a retenção do tópico. |
| `processing` | Em execução ou aguardando retomada após uma falha transitória. |
| `completed` | Texto disponível na coluna privada `text`. `finished_at` registra a conclusão em UTC. |
| `failed` | Falha permanente com `finished_at` e `failure_code`, sem texto. O consumidor confirma o offset depois de persistir o diagnóstico. |

Os códigos permanentes incluem `hash_mismatch`, `stale_file`, `corrupt_pdf`, `encrypted_pdf`, `no_text`, `too_large`, `page_limit`, `text_limit` e `time_limit`. O worker limita a entrada a 20 MiB, o documento a 500 páginas, o texto a um milhão de caracteres e o subprocesso a 45 segundos. Em Linux há também um teto de 512 MiB de memória virtual para o subprocesso. No Windows o limite de tempo e os limites de conteúdo não garantem um teto de memória. PDFs digitalizados sem camada textual terminam com `no_text`. Não há OCR.

Em falhas de banco, armazenamento, confirmação Kafka ou envelope de submissão inválido, o comando encerra com erro e informa tópico, partição e offset quando disponíveis. Para retomar, restaure o banco ou o acesso ao arquivo e reinicie com o mesmo grupo. Em caso de versão desconhecida, atualize o consumidor antes de reiniciar. Uma mensagem irrecuperável exige intervenção do operador para registrar a ocorrência e decidir sobre o avanço do offset dessa partição. O worker não repete indefinidamente nem pula automaticamente esse registro. O Redis continua com apenas o estado temporário do upload.

A migration `0004_pdf_extraction` prepara também registros pendentes para submissões históricas identificadas na Outbox e com arquivo associado. A recuperação automática dessas submissões depende de o evento ainda estar retido no Kafka. A migration não republica eventos.

### Teste manual no Windows com Docker Desktop

1. Com o Docker Desktop em execução, use os comandos de instalação e Compose da seção **Ambiente local**. Ative o ambiente Python em cada terminal. Aplique `python manage.py migrate` e confira `python manage.py showmigrations thesis`.
2. Abra três terminais no diretório do serviço. Execute a API com `python manage.py runserver`, o publicador com `python manage.py run_outbox_worker` e o consumidor com `python manage.py run_pdf_worker`. Use Ctrl+C para encerrar o consumidor após a mensagem em andamento.
3. Com tokens compatíveis com o contrato, crie um rascunho, preencha resumo e palavras-chave, associe o orientador como coordenador e envie um PDF com texto como estudante. Envie `POST /api/theses/{id}/submit/` com o token do titular. Para observar `pending`, submeta enquanto o consumidor estiver parado e inicie-o depois.
4. Consulte o resultado pelo shell administrativo local. Substitua o UUID abaixo pelo da monografia. A consulta exibe apenas o estado, o diagnóstico e o tamanho, sem imprimir o texto acadêmico.

```powershell
python manage.py shell -c "from django.db.models.functions import Length; from thesis.models import PdfExtractionModel; print(PdfExtractionModel.objects.filter(thesis_id='00000000-0000-0000-0000-000000000000').annotate(chars=Length('text')).values('status','finished_at','failure_code','chars').first())"
```

Para validar com um broker real sem emitir tokens, execute o teste de integração opcional. Ele usa um banco de teste e cria e remove seu próprio tópico temporário. A conta Kafka precisa dessas permissões. O grupo usado no teste também é exclusivo.

```powershell
$env:TEST_KAFKA_BOOTSTRAP_SERVERS = '127.0.0.1:9092'
python manage.py test thesis.tests.test_pdf_worker.KafkaPdfIntegrationTests
Remove-Item Env:TEST_KAFKA_BOOTSTRAP_SERVERS
```

## Verificação

Execute os comandos abaixo no diretório do serviço, com PostgreSQL e Redis disponíveis. O usuário PostgreSQL precisa poder criar o banco temporário de testes. Os testes HTTP usam um emissor de teste com chaves geradas durante a execução. Os testes de publicação simulam o produtor Kafka.

```console
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Se um banco de teste anterior já existir, `python manage.py test --keepdb` o reaproveita sem pedir confirmação para apagá-lo. `thesis.tests.test_rate_limit` cobre cota, isolamento por conta e operação, expiração, concorrência com 30 clientes Redis e falha de conexão. `thesis.tests.test_upload_protection` cobre as respostas 429 e 503, o consumo de cota apenas após validação e os cenários de deduplicação, integridade, falha do PostgreSQL, lock concorrente e status. Os testes de integração usam contas aleatórias e removem as chaves de cota ao terminar. O teste Kafka real é opcional e fica ignorado sem `TEST_KAFKA_BOOTSTRAP_SERVERS`.

## Limitações de segurança

- Não há emissor de tokens neste serviço. A confiança depende da chave pública, do emissor e do público-alvo configurados, e a revogação de tokens antes de `exp` depende do futuro `identity-service`.
- O controle de taxa usa janela fixa e permite rajadas de até duas cotas na virada da janela. Ele limita por conta, não por IP. A proteção contra volume não autenticado depende de proxy reverso ou WAF.
- O corpo multipart é recebido pelo Django antes da validação do caso de uso. O limite de 20 MiB também deve ser aplicado no proxy reverso.
- A validação de PDF verifica assinatura e tamanho. A análise estrutural e a extração ficam no worker isolado, e não há antivírus.
- O armazenamento é um volume local compartilhado. Arquivos substituídos ou órfãos não são removidos automaticamente.
- Redis, PostgreSQL e Kafka usam listeners sem TLS na configuração local.
