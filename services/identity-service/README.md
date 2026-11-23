# Serviço de identidade

O `identity-service` autentica contas acadêmicas por e-mail e senha e emite tokens de acesso JWT RS256 aceitos pelo `thesis-service`. O serviço é dono das contas, dos papéis, dos vínculos acadêmicos e da chave privada de assinatura. Os demais serviços recebem somente a chave pública e não acessam as tabelas deste serviço.

Esta é a primeira etapa: login, emissão do token e consulta do próprio perfil. Contas são provisionadas por um comando administrativo. Não há cadastro público, recuperação de senha, refresh token nem painel administrativo.

## Estrutura

| Caminho | Responsabilidade |
| --- | --- |
| `identity/domain` | Conta imutável, papéis acadêmicos e regras de provisionamento e de elegibilidade ao token. |
| `identity/application` | Portas e casos de uso: emitir token, consultar perfil e provisionar conta. |
| `identity/adapters/inbound/rest` | API REST, autenticação Bearer do próprio serviço e serializers. |
| `identity/adapters/outbound/persistence` | Modelo de usuário customizado e repositório Django. |
| `identity/adapters/outbound/allauth` | Verificação de credenciais com django-allauth e adapter com cadastro fechado. |
| `identity/adapters/outbound/security` | Carregamento da chave RSA, assinatura e verificação JWT. |
| `identity/management/commands` | `create_academic_user` e `export_jwt_public_key`. |
| `config` | Configuração Django, rotas e composição de dependências. |

## Modelo de conta

A tabela `identity_user` usa o modelo customizado `identity.User` (`AUTH_USER_MODEL`), definido desde a primeira migration.

| Campo | Regra |
| --- | --- |
| `id` | UUID da conta, emitido como `sub`. |
| `academic_id` | UUID acadêmico próprio, diferente de `id`. Pode ser informado no provisionamento para preservar um vínculo existente. |
| `name`, `email` | E-mail normalizado em minúsculas e único sem diferenciar maiúsculas (constraint `Lower(email)`). |
| `password` | Hash PBKDF2-SHA256 com sal do Django. A senha nunca é gravada em texto puro. |
| `role` | `student`, `advisor`, `coordinator` ou `admin`, validado também por constraint. |
| `course_id` | Obrigatório para todos os papéis, exceto `admin`. Garantido por constraint. |
| `is_active` | Contas inativas não fazem login e perdem o acesso ao perfil. |

Cada conta recebe um `EmailAddress` do allauth verificado e primário. Senhas passam pelos validadores do Django, com mínimo de 12 caracteres.

## django-allauth

A versão 65.22.1 declara suporte a Python 3.14 e Django 6.1. O serviço usa `allauth.account` com `ACCOUNT_LOGIN_METHODS = {"email"}` e sem campo de nome de usuário. A verificação de credenciais passa por `DefaultAccountAdapter.authenticate` e `AuthenticationBackend`, que fornecem:

- consulta por e-mail sem diferenciar maiúsculas;
- mitigação de enumeração por tempo, com hash fictício quando o e-mail não existe;
- limitação de tentativas falhas (`login_failed`), por padrão `10/m/ip,5/5m/key`, armazenada no Redis (`IDENTITY_REDIS_URL`, banco 1) e compartilhada entre os workers Gunicorn.

O allauth devolve contas inativas com senha correta para seus próprios fluxos HTML. O adapter `AllauthCredentialVerifier` recusa essas contas. `ClosedSignupAccountAdapter` fecha o cadastro e as URLs HTML do allauth não são publicadas. Como as contas são provisionadas pela administração, `ACCOUNT_EMAIL_VERIFICATION` é `none`.

## API

| Método e rota | Entrada ou resultado |
| --- | --- |
| `POST /api/auth/login/` | JSON com `email` e `password`. Retorna `access_token`, `token_type=Bearer` e `expires_in`, com `Cache-Control: no-store`. |
| `GET /api/auth/me/` | Exige `Authorization: Bearer <token>`. Retorna `id`, `name`, `email`, `role`, `academic_id`, `course_id` e `is_active` lidos do banco. |

| Situação | Resposta |
| --- | --- |
| Senha incorreta, e-mail inexistente ou conta inativa | 401 com a mesma mensagem genérica |
| Campos extras no login, como `role`, `academic_id` ou `course_id` | 400, sem emissão de token |
| Conta sem curso ou com orientadores acima do teto | 403 |
| Excesso de tentativas falhas | 429 |
| Chave, emissor ou público-alvo ausentes ou chave inválida | 503 |
| Token ausente, inválido, expirado ou de conta desativada em `/me/` | 401 |

## Contrato JWT emitido

O token segue o contrato de [IDENTITY.md](../thesis-service/IDENTITY.md) do serviço de monografias. O cabeçalho é `{"alg": "RS256", "typ": "at+jwt"}` e o algoritmo é fixo no emissor e no verificador.

| Claim | Origem |
| --- | --- |
| `iss`, `aud` | `IDENTITY_JWT_ISSUER` e `IDENTITY_JWT_AUDIENCE`, com `aud` como string única. |
| `sub` | `User.id`. |
| `academic_id`, `role`, `course_id` | Valores gravados na conta. Nada vem do corpo da requisição. |
| `iat`, `exp` | Segundos inteiros. A duração é `IDENTITY_ACCESS_TOKEN_TTL_SECONDS`, padrão 300 e permitida entre 60 e 3600. |
| `jti` | UUID aleatório por token, reservado para auditoria ou revogação futura. |
| `assignable_advisor_ids` | Somente para `coordinator`. Ver a política abaixo. |

**Política de `assignable_advisor_ids`.** A lista contém os `academic_id` das contas `advisor` ativas do mesmo `course_id` do coordenador. Esses vínculos vêm das contas provisionadas pela administração, e nenhum usuário pode editá-los. Outros papéis não recebem a claim, e o thesis-service assume lista vazia. Se houver mais orientadores que `IDENTITY_MAX_ASSIGNABLE_ADVISORS` (padrão 100, máximo 300), o login do coordenador falha com 403 em vez de truncar a lista. Critérios adicionais de elegibilidade, como carga de orientação ou área, exigirão uma fonte própria em etapa futura.

O `/me/` deste serviço aceita somente tokens emitidos com a própria chave, emissor e público-alvo, e consulta o banco a cada requisição. O thesis-service continua validando apenas a assinatura e as claims até `exp`, conforme o contrato.

## Configuração

O serviço lê variáveis de ambiente e o `.env` da raiz do repositório.

| Variáveis | Uso |
| --- | --- |
| `IDENTITY_SECRET_KEY`, `IDENTITY_DEBUG`, `IDENTITY_ALLOWED_HOSTS` | Chave Django própria, depuração (desativada por padrão) e hosts aceitos. |
| `IDENTITY_DB_NAME`, `IDENTITY_DB_USER`, `IDENTITY_DB_PASSWORD`, `IDENTITY_DB_HOST`, `IDENTITY_DB_PORT` | Banco próprio. Padrões `identity_db`, `identity_user`, `127.0.0.1` e `5434`. |
| `IDENTITY_REDIS_URL` | Cache dos limites de login. Padrão `redis://127.0.0.1:6379/1`. |
| `IDENTITY_JWT_ISSUER`, `IDENTITY_JWT_AUDIENCE` | Emissor e público-alvo. Devem ser iguais a `THESIS_JWT_ISSUER` e `THESIS_JWT_AUDIENCE`. |
| `IDENTITY_JWT_PRIVATE_KEY_FILE`, `IDENTITY_JWT_PRIVATE_KEY` | Caminho do PEM privado (preferível) ou PEM em variável, com `\n` aceito. O arquivo prevalece. |
| `IDENTITY_ACCESS_TOKEN_TTL_SECONDS`, `IDENTITY_MAX_ASSIGNABLE_ADVISORS`, `IDENTITY_LOGIN_FAILED_RATE` | Duração do token, teto da lista de orientadores e limite de falhas do allauth. |

### Chaves RSA

A chave privada fica somente com este serviço, **fora do repositório** (o `.gitignore` também ignora `*.pem` e `*.key`). O serviço aceita PEM RSA sem senha com pelo menos 2048 bits e recusa chaves fracas, cifradas ou inválidas. Sem chave válida, o login responde 503, o `/me/` responde 401 e os comandos administrativos de contas continuam funcionando. Para gerar uma chave de 3072 bits:

```powershell
New-Item -ItemType Directory -Force C:\chaves | Out-Null
python -c "import sys; from cryptography.hazmat.primitives import serialization as s; from cryptography.hazmat.primitives.asymmetric import rsa; k = rsa.generate_private_key(public_exponent=65537, key_size=3072); open(sys.argv[1], 'wb').write(k.private_bytes(s.Encoding.PEM, s.PrivateFormat.PKCS8, s.NoEncryption()))" C:/chaves/identity-private.pem
```

No Linux, use `openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out identity-private.pem` e restrinja com `chmod 600`. Para obter a chave pública e entregá-la ao thesis-service:

```sh
python manage.py export_jwt_public_key > identity-public.pem
```

Configure no thesis-service `THESIS_JWT_PUBLIC_KEY_HOST_FILE` com esse arquivo (Compose com `compose.jwt-file.yaml`) ou `THESIS_JWT_PUBLIC_KEY`, além de `THESIS_JWT_ISSUER` e `THESIS_JWT_AUDIENCE` iguais aos do identity. A rotação exige trocar as duas pontas e reiniciar os serviços. Tokens assinados pela chave antiga deixam de valer.

## Instalação local

Execute a partir de `services/identity-service`, com o ambiente virtual ativado:

```powershell
python -m pip install -r requirements.txt
python manage.py check
python manage.py migrate
python manage.py runserver 127.0.0.1:8002
```

## Banco de dados

O serviço usa o banco `identity_db` e a role `identity_user` no mesmo servidor PostgreSQL 18, sem compartilhar tabelas com o `thesis_db`. O serviço Compose `identity-db-init` executa [identity-db.sql](../../infrastructure/postgres/identity-db.sql) com o superusuário configurado. O script cria a role e o banco apenas se não existirem, revoga o acesso público ao banco e concede conexão à role. Ele não remove, recria nem altera dados existentes. Uma nova execução é segura.

A role recebe `CREATEDB` para que `python manage.py test` possa criar `test_identity_db` no ambiente local. Em produção, remova esse atributo com `ALTER ROLE identity_user NOCREATEDB` e execute os testes com outra credencial. Para trocar a senha, use `ALTER ROLE ... PASSWORD` e atualize `IDENTITY_DB_PASSWORD`.

## Docker Compose

Os serviços de identidade ficam em `infrastructure/compose.identity.yaml`, separados do arquivo principal. Os comandos existentes do thesis-service continuam iguais. Execute na raiz do repositório:

```sh
docker compose --env-file .env -f infrastructure/compose.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml config --quiet
docker compose --env-file .env -f infrastructure/compose.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml build identity-api
docker compose --env-file .env -f infrastructure/compose.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml up -d --wait identity-api
```

`compose.identity-key.yaml` monta o arquivo indicado em `IDENTITY_JWT_PRIVATE_KEY_HOST_FILE` (caminho absoluto) como secret somente leitura em `/run/secrets/identity_jwt_private_key`. O arquivo precisa estar legível pelo UID 10001. A ordem de inicialização é `identity-db-init`, `identity-migrate` e `identity-api`. A API publica em `127.0.0.1:8002` (`IDENTITY_API_PORT`) e fica saudável quando `/api/auth/me/` responde 401 sem token. Na rede interna do Compose, o endereço é `http://identity-api:8000`. Nenhum volume novo é criado. Para parar só este serviço, use `stop identity-api`.

## Criação de usuários

Contas são criadas somente por quem tem acesso administrativo ao serviço. A senha é solicitada duas vezes no terminal ou lida da entrada padrão com `--password-stdin`, e nunca aparece na saída nem nos argumentos.

```powershell
python manage.py create_academic_user --email ana@exemplo.edu --name "Ana Souza" --role student --course-id 00000000-0000-0000-0000-000000000000
```

Opções adicionais: `--academic-id` para reutilizar um UUID acadêmico existente e `--inactive`. No Compose, use `docker compose ... exec identity-api python manage.py create_academic_user ...`. O comando imprime `account_id` e `academic_id`.

## Login e uso do token

```powershell
$body = @{ email = "ana@exemplo.edu"; password = Read-Host "Senha" } | ConvertTo-Json
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8002/api/auth/login/ -ContentType application/json -Body $body
Invoke-RestMethod -Uri http://127.0.0.1:8002/api/auth/me/ -Headers @{ Authorization = "Bearer $($login.access_token)" }
```

Com o thesis-service configurado com a mesma chave pública, emissor e público-alvo, o mesmo cabeçalho é aceito em `/api/theses/`.

## Testes

Execute no diretório do serviço, com PostgreSQL disponível e a role com permissão para criar o banco de teste:

```console
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Os testes geram chaves RSA em memória e usam cache local isolado. Eles cobrem hash de senha, normalização e unicidade do e-mail, constraints, cadastro fechado, login válido e inválido, conta inativa, e-mail inexistente, campos privilegiados no corpo, limitação de tentativas, chave ausente ou inválida, cabeçalho e claims do JWT, expiração, papéis, separação entre `sub` e `academic_id`, a política de orientadores e o perfil autenticado.

`identity.tests.test_thesis_compatibility` executa em subprocesso o `AcademicTokenAuthentication` original do thesis-service, com as configurações dele, sobre tokens emitidos pelo login real. O teste confirma a aceitação, os valores da identidade acadêmica e a recusa de uma chave não confiável. Ele é ignorado quando o código do thesis-service não está presente, como dentro da imagem do identity.

## Segurança e limitações

- Não há refresh token nem revogação. Um token continua válido no thesis-service até `exp`, mesmo após desativar a conta. Por isso a duração é curta.
- Coordenadores e administradores atuam em um único curso por conta. O token para outro curso exige outra conta ou um modelo futuro de vínculos múltiplos.
- O limite de falhas usa `REMOTE_ADDR`. Atrás de um proxy reverso, configure `ALLAUTH_TRUSTED_PROXY_COUNT` ou o cabeçalho confiável do allauth, ou o limite por IP passará a valer para o proxy.
- Logins bem-sucedidos não são limitados nem auditados nesta etapa.
- A configuração local usa HTTP e PostgreSQL e Redis sem TLS. Em implantação, o login exige HTTPS.

## Integração futura

- **thesis-service:** configurar a chave pública e o mesmo emissor e público-alvo em `.env`. O contrato não mudou.
- **Outros serviços:** podem validar o mesmo token com a chave pública. Públicos-alvo por serviço podem ser adotados quando o contrato for estendido.
- **Próximas etapas:** gestão de usuários com autorização de administrador, usuários externos temporários, recuperação de senha por e-mail, refresh tokens com rotação e revogação, publicação de JWKS para rotação de chaves, auditoria de autenticação e eventos Kafka de ciclo de vida das contas.
