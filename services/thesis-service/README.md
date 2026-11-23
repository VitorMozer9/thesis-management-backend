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

## Ambiente local

Use Python 3.14. A infraestrutura de desenvolvimento em `../../infrastructure/compose.yaml` publica PostgreSQL 18 em `127.0.0.1:5434`, Redis 7.4 em `127.0.0.1:6379` e Kafka 4.4 em `127.0.0.1:9092`. API, publicador da Outbox e consumidor de PDFs são processos separados.

O serviço lê variáveis de ambiente e carrega o arquivo `.env` da raiz do repositório. Preencha as credenciais com valores próprios do ambiente. Use o mesmo banco, tópico e configuração de conexão para API e worker.

| Variáveis | Uso |
| --- | --- |
| `DJANGO_SECRET_KEY`, `DJANGO_DEBUG` | Chave obrigatória do Django e depuração opcional, desativada por padrão. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Nome do banco e credenciais obrigatórios. |
| `DB_HOST`, `DB_PORT` | Host e porta do PostgreSQL. Padrões locais `127.0.0.1` e `5434`. |
| `REDIS_URL` | Conexão para locks e estado do upload. Padrão `redis://127.0.0.1:6379/0`. |
| `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_THESIS_EVENTS_TOPIC` | Endereço inicial do broker e tópico. Padrões `localhost:9092` e `thesis.events.v1`. |
| `KAFKA_PDF_GROUP_ID` | Grupo exclusivo do consumidor de submissões. Padrão `thesis-pdf-extraction-v1`. |
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
