# Ambiente Docker integrado

Para iniciar os cinco microsserviços, o frontend e o Mailpit, siga o [guia de execução completo](../docs/GUIA_EXECUCAO.md).

Este guia inicia o `thesis-service` e o `identity-service` juntos no ambiente local, com o identity assinando tokens JWT RS256 e o thesis validando esses tokens pela chave pública. Os comandos são executados **na raiz do repositório**, com Docker Desktop em modo Linux ou Docker Engine com Compose v2.

## Composição

A composição integrada usa quatro arquivos, sempre nesta ordem:

| Arquivo | Conteúdo |
| --- | --- |
| `compose.yaml` | PostgreSQL 18, Redis 7.4, Kafka 4.4, migrations e tópico do thesis, `thesis-api`, `thesis-outbox-worker` e `thesis-pdf-worker`. |
| `compose.jwt-file.yaml` | Monta a chave **pública** como secret somente no `thesis-api`. |
| `compose.identity.yaml` | `identity-db-init`, `identity-migrate` e `identity-api`. |
| `compose.identity-key.yaml` | Monta a chave **privada** como secret somente no `identity-api`. |

Defina um atalho para a sessão. PowerShell:

```powershell
function dc { docker compose --env-file .env -f infrastructure/compose.yaml -f infrastructure/compose.jwt-file.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml @args }
```

Linux ou Git Bash:

```sh
alias dc='docker compose --env-file .env -f infrastructure/compose.yaml -f infrastructure/compose.jwt-file.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml'
```

| Serviço | Endereço no host | Endereço interno |
| --- | --- | --- |
| `thesis-api` | `http://127.0.0.1:8001` (`THESIS_API_PORT`) | `http://thesis-api:8000` |
| `identity-api` | `http://127.0.0.1:8002` (`IDENTITY_API_PORT`) | `http://identity-api:8000` |
| PostgreSQL | `127.0.0.1:5434` | `postgres:5432` |
| Redis | `127.0.0.1:6379` | `redis:6379` |
| Kafka | `127.0.0.1:9092` | `kafka:19092` |

Os bancos são separados no mesmo servidor: `thesis_db` e `identity_db`, cada um com sua role. O Redis usa o banco 0 para o thesis e o banco 1 para os limites de login do identity.

## Chaves RSA

A chave de desenvolvimento fica em um diretório privado do usuário, fora do repositório e de pastas temporárias:

| Arquivo | Uso | Acesso |
| --- | --- | --- |
| `%USERPROFILE%\.thesis-management\keys\identity-private.pem` | Assinatura no `identity-api` | Leitura somente pelo usuário local. Herança de ACL removida. |
| `%USERPROFILE%\.thesis-management\keys\identity-public.pem` | Verificação no `thesis-api` | Material público. |

Para criar as chaves em uma máquina nova, gere a privada conforme [o README do identity](../services/identity-service/README.md#chaves-rsa) e restrinja o acesso:

```powershell
$keys = Join-Path $env:USERPROFILE ".thesis-management\keys"
icacls (Split-Path $keys) /inheritance:r /grant:r "${env:USERNAME}:(OI)(CI)F"
icacls "$keys\identity-private.pem" /inheritance:r /grant:r "${env:USERNAME}:R"
```

No Linux, use `chmod 700` no diretório e `chmod 600` na chave. Exporte a pública com o comando do próprio serviço. A partir de `services/identity-service`, com `IDENTITY_JWT_PRIVATE_KEY_FILE` apontando para a chave privada:

```powershell
$env:IDENTITY_JWT_PRIVATE_KEY_FILE = "$env:USERPROFILE\.thesis-management\keys\identity-private.pem"
python manage.py export_jwt_public_key | Set-Content -Encoding ascii "$env:USERPROFILE\.thesis-management\keys\identity-public.pem"
Remove-Item Env:IDENTITY_JWT_PRIVATE_KEY_FILE
```

Preencha no `.env`, com caminhos absolutos e barras normais:

```dotenv
IDENTITY_JWT_ISSUER=urn:tcc:identity
IDENTITY_JWT_AUDIENCE=urn:tcc:api
THESIS_JWT_ISSUER=urn:tcc:identity
THESIS_JWT_AUDIENCE=urn:tcc:api
IDENTITY_JWT_PRIVATE_KEY_HOST_FILE=C:/Users/<usuario>/.thesis-management/keys/identity-private.pem
THESIS_JWT_PUBLIC_KEY_HOST_FILE=C:/Users/<usuario>/.thesis-management/keys/identity-public.pem
```

O Compose entrega cada arquivo como secret em `/run/secrets/`. A chave privada não entra na imagem (o `.dockerignore` exclui `*.pem` e `*.key`) nem no `thesis-api`. Para confirmar que as duas pontas usam o mesmo par, compare as impressões digitais. Nenhum material privado é exibido:

```sh
dc exec -T identity-api python manage.py export_jwt_public_key | sha256sum
dc exec -T thesis-api sh -c 'sha256sum < /run/secrets/thesis_jwt_public_key'
```

**Rotação.** Gere um novo par, substitua os dois arquivos e recrie as APIs com `dc up -d --force-recreate --no-deps identity-api thesis-api`. O Compose não detecta a troca do conteúdo ou do caminho de um secret, por isso é necessário `--force-recreate`. Tokens emitidos com a chave anterior deixam de valer.

## Inicialização

```sh
dc config --quiet
dc build thesis-api identity-api
dc up -d --wait
dc ps -a
```

`thesis-migrate`, `thesis-topic`, `identity-db-init` e `identity-migrate` são tarefas de inicialização e terminam com código zero. `identity-db-init` cria `identity_db` e `identity_user` somente se ainda não existirem. As APIs ficam saudáveis quando as rotas protegidas respondem 401 sem token. Os workers não têm healthcheck. Confira o estado com `dc ps` e os logs com `dc logs --tail 50 thesis-outbox-worker thesis-pdf-worker`.

## Usuários de desenvolvimento

O script abaixo usa o comando `create_academic_user` dentro do `identity-api`. Ele cria, somente se ainda não existirem, seis contas sintéticas no mesmo curso, todas `@example.invalid`:

- `dev-student`, `dev-advisor` e `dev-coordinator`;
- `dev-other-student` e `dev-other-advisor`, usadas nos testes de acesso a recursos alheios;
- `dev-admin`, para a administração de contas em `/api/users/`.

Contas acrescentadas ao script depois são completadas sem alterar as existentes.

```sh
python infrastructure/e2e/provision_dev_users.py
```

Na primeira execução, o script gera senhas aleatórias e um `course_id` e grava esses dados em `%USERPROFILE%\.thesis-management\dev-users.json`. O arquivo herda a ACL restrita do diretório. A variável `THESIS_DEV_USERS_FILE` permite escolher outro caminho. A saída mostra e-mail, papel e `academic_id`, sem senhas. Execuções seguintes reutilizam o arquivo e não alteram contas existentes. As contas são criadas no `identity_db` local, que só contém dados de desenvolvimento.

O coordenador recebe em `assignable_advisor_ids` os orientadores ativos do mesmo curso. Não existe rota pública de cadastro, e o login recusa campos como `role` no corpo.

## Login e Bearer token

```powershell
$users = Get-Content "$env:USERPROFILE\.thesis-management\dev-users.json" | ConvertFrom-Json
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8002/api/auth/login/ -ContentType application/json -Body (@{ email = $users.accounts.student.email; password = $users.accounts.student.password } | ConvertTo-Json)
$auth = @{ Authorization = "Bearer $($login.access_token)" }
Invoke-RestMethod -Uri http://127.0.0.1:8002/api/auth/me/ -Headers $auth
Invoke-RestMethod -Uri http://127.0.0.1:8001/api/theses/ -Headers $auth
```

O token dura `IDENTITY_ACCESS_TOKEN_TTL_SECONDS` (padrão 300 s). Depois disso, faça login novamente.

## Teste ponta a ponta

```sh
python infrastructure/e2e/academic_flow.py
```

O script usa somente tokens emitidos pelo `identity-api`. Ele valida:

1. o login do estudante e `/api/auth/me/`;
2. a criação do rascunho e as palavras-chave;
3. a associação do orientador pelo coordenador;
4. o upload de um PDF textual e a submissão;
5. a publicação de `thesis.created` e `thesis.submitted` pela Outbox;
6. a extração do texto pelo worker via Kafka;
7. a recusa de aprovação pelo orientador não vinculado e a aprovação pelo vinculado;
8. a publicação de `thesis.advisor_approved`;
9. a sequência completa da auditoria, com o `sub` de cada ator.

Também verifica:

- requisição sem token, token adulterado e claims alteradas: 401;
- senha incorreta: 401;
- papel enviado no login: 400;
- acesso de outro estudante: negado;
- ausência de rotas públicas de cadastro;
- por fim, aguarda a **expiração natural** do primeiro token e confirma 401 nos dois serviços.

`--skip-expiration` dispensa essa espera. `--previous-thesis <uuid>` confirma também que uma monografia aprovada anteriormente continua disponível.

As consultas à Outbox, à extração e à auditoria usam `manage.py shell` dentro do `thesis-api` e não exibem o texto do PDF. Cada execução cria uma monografia sintética e o PDF correspondente no volume `thesis_media`, e esses dados permanecem gravados.

Emissor e público-alvo incorretos são cobertos pelos testes automatizados dos dois serviços. Para confirmar no ambiente real, assine com o código do identity alterando somente essas claims:

```sh
dc exec -T identity-api python manage.py shell -c "
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from django.test import override_settings
from config import dependencies
from identity.models import User
from identity.adapters.outbound.persistence.django_account_repository import to_account
account = to_account(User.objects.get(email='dev-student@example.invalid'))
for changes in ({'IDENTITY_JWT_ISSUER': 'urn:tcc:untrusted'}, {'IDENTITY_JWT_AUDIENCE': 'urn:tcc:other'}):
    with override_settings(**changes):
        use_case = dependencies.build_issue_access_token_use_case(None)
        token = use_case.signer.sign(use_case.claims_for(account))
    try:
        print(urlopen(Request('http://thesis-api:8000/api/theses/', headers={'Authorization': 'Bearer ' + token})).status)
    except HTTPError as error:
        print(error.code)
"
```

## Reinicialização sem perda de dados

```sh
dc restart identity-api thesis-api thesis-outbox-worker thesis-pdf-worker
dc ps
python infrastructure/e2e/academic_flow.py --skip-expiration --previous-thesis <uuid>
```

`restart` mantém contêineres, secrets e volumes. Para recriar contêineres após mudar imagem ou configuração, use `dc up -d --wait`. Se apenas um secret mudou, acrescente `--force-recreate --no-deps` com os serviços afetados. Para parar tudo sem perder dados, use `dc stop`. **Não use `down -v` nem `volume prune`**: eles removem bancos, tópicos e PDFs.

O consumo do Kafka pode ser conferido pelo grupo do worker de PDF:

```sh
dc exec -T kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server kafka:19092 --describe --group thesis-pdf-extraction-v1
```

## Limitações conhecidas

- O transporte local é HTTP. PostgreSQL, Redis e Kafka não usam TLS.
- Não há refresh token, revogação, JWKS nem rotação sem indisponibilidade. Um token continua válido no thesis-service até `exp`, mesmo depois de a conta ser desativada.
- O `POSTGRES_USER` da imagem oficial, usado pelo `thesis-service`, é superusuário. Em um ambiente compartilhado, crie uma role própria e sem privilégios administrativos para o thesis. A role `identity_user` não lê nenhuma tabela do `thesis_db`, mas, pelo padrão do PostgreSQL, ainda pode conectar-se a ele. `REVOKE CONNECT ON DATABASE thesis_db FROM PUBLIC` encerra esse acesso.
- `identity_user` tem `CREATEDB` apenas para os testes locais. Veja [o README do identity](../services/identity-service/README.md#banco-de-dados).
- As senhas de desenvolvimento ficam em texto no arquivo privado do usuário. Esse arquivo não deve ser usado para contas reais.
