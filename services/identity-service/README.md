# Serviço de identidade

O `identity-service` autentica contas acadêmicas por e-mail e senha e emite tokens de acesso JWT RS256 aceitos pelo `thesis-service`. O serviço é dono das contas, dos papéis, dos vínculos acadêmicos e da chave privada de assinatura. Os demais serviços recebem somente a chave pública e não acessam as tabelas deste serviço.

O serviço oferece login, emissão do token, consulta do próprio perfil e administração de contas acadêmicas por administradores ativos. Não há cadastro público, recuperação de senha, convite, refresh token nem painel HTML.

## Estrutura

| Caminho | Responsabilidade |
| --- | --- |
| `identity/domain` | Conta imutável, papéis acadêmicos e regras de provisionamento, alteração e elegibilidade ao token. |
| `identity/application` | Portas, regras de autorização administrativa e casos de uso: emitir token, consultar perfil, provisionar, criar, consultar, listar, atualizar, ativar e desativar contas. |
| `identity/adapters/inbound/rest` | API REST, autenticação Bearer do próprio serviço, permissão administrativa e serializers. |
| `identity/adapters/outbound/persistence` | Modelo de usuário customizado, repositório com bloqueios, unidade de trabalho e auditoria administrativa. |
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
| `GET /api/users/` | Administração. Lista contas com filtros e paginação. |
| `POST /api/users/` | Administração. Cria conta não administrativa. Responde 201 com `Location`. |
| `GET /api/users/{id}/` | Administração. Consulta uma conta pelo UUID. |
| `PATCH /api/users/{id}/` | Administração. Altera `name`, `email`, `role` ou `course_id`. |
| `POST /api/users/{id}/deactivate/` e `POST /api/users/{id}/activate/` | Administração. Corpo vazio. Operações idempotentes. |

As respostas de conta usam sempre os sete campos de `/api/auth/me/`. Senha, hash, `last_login` e outros atributos internos nunca são devolvidos. Todas as respostas que contêm tokens ou dados de conta usam `Cache-Control: no-store`.

| Situação | Resposta |
| --- | --- |
| Senha incorreta, e-mail inexistente ou conta inativa | 401 com a mesma mensagem genérica |
| Campos extras no login, como `role`, `academic_id` ou `course_id` | 400, sem emissão de token |
| Conta sem curso ou com orientadores acima do teto | 403 |
| Excesso de tentativas falhas | 429 |
| Chave, emissor ou público-alvo ausentes ou chave inválida | 503 |
| Token ausente, inválido, expirado ou de conta desativada em `/me/` | 401 |

## Administração de contas

### Autorização

Somente contas com `role=admin` e `is_active=true` **no banco** administram contas. A cada requisição, a permissão `IsActiveAdministrator` carrega o ator pelo `sub` do token verificado e confere papel e estado atuais. O `role` do JWT nunca é usado para autorizar. As operações de escrita repetem essa verificação dentro da transação, com a linha do ator bloqueada.

| Ator | Resultado |
| --- | --- |
| Sem token ou token inválido | 401 |
| Administrador desativado, mesmo com JWT ainda dentro de `exp` | 401 |
| `student`, `advisor` ou `coordinator` | 403. A coordenação não herda privilégios de administração de contas. |
| Administrador ativo | Autorizado, com as restrições abaixo |

| Restrição | Resposta |
| --- | --- |
| Criar conta `admin` pela API | 403. Administradores só são provisionados por `create_academic_user`. |
| Promover alguém a `admin` ou alterar o papel de um administrador, inclusive o próprio | 403 |
| Desativar a própria conta | 403 |
| Desativar o último administrador ativo | 409 |
| Alterar `id`, `academic_id`, `is_active` ou senha por `PATCH`, ou enviar campos não declarados | 400 |
| Conta inexistente | 404 |
| Excluir conta | Sem rota. Contas são desativadas, nunca removidas. |

Um administrador precisa ter `course_id` para obter token, porque essa claim é obrigatória no contrato JWT. Contas `admin` sem curso continuam válidas para a CLI, mas não acessam a API.

### Concorrência

Criação, alteração, ativação e desativação executam em uma transação PostgreSQL. No início, uma única consulta `SELECT ... FOR UPDATE ORDER BY id` bloqueia o ator, a conta afetada e todas as contas administrativas ativas. A ordem fixa evita deadlocks. A segunda transação concorrente aguarda e reavalia o estado já confirmado. Assim, dois administradores que tentam desativar um ao outro ao mesmo tempo não deixam o sistema sem administrador: a segunda operação encontra o próprio ator desativado e falha com 401. Alterações simultâneas na mesma conta também são serializadas, e cada registro de auditoria parte do valor confirmado anteriormente.

### Criação de contas e senha inicial

`POST /api/users/` usa o mesmo caso de uso do comando `create_academic_user` (`ProvisionAccountUseCase`). Por isso as mesmas validações valem nos dois caminhos:

- e-mail válido, normalizado e único sem diferenciar maiúsculas;
- nome entre 1 e 150 caracteres;
- papel válido;
- curso obrigatório para papéis diferentes de `admin`;
- `academic_id` opcional, válido e único;
- senha conforme os validadores do Django (mínimo de 12 caracteres, sem semelhança com nome ou e-mail, nem comum, nem só numérica).

| Campo | Regra |
| --- | --- |
| `name`, `email`, `role`, `password` | Obrigatórios. `role` aceita `student`, `advisor` ou `coordinator`. |
| `course_id` | Obrigatório para esses papéis. |
| `academic_id` | Opcional. Informe somente para preservar um identificador acadêmico já usado por outros sistemas. Caso contrário, o serviço gera um UUID. |

**Política de senha inicial.** Como ainda não existem convite, recuperação nem troca de senha, o administrador define uma senha inicial forte e a entrega ao titular por canal separado e seguro. A senha é `write_only`, recebe hash PBKDF2 antes de ser gravada e não aparece em respostas, mensagens de erro, auditoria ou logs da aplicação. O serviço não força a troca no primeiro acesso, porque essa função ainda não existe. Fora do ambiente local, a API **exige HTTPS**, já que a senha trafega no corpo da requisição.

### Alteração de vínculos acadêmicos

`PATCH` aceita somente `name`, `email`, `role` (entre `student`, `advisor` e `coordinator`) e `course_id`. As regras do domínio e as constraints do banco continuam valendo, por exemplo curso obrigatório fora de `admin`. A troca de e-mail também atualiza o `EmailAddress` primário do allauth, e o login passa a usar o novo endereço.

- `id` e `academic_id` são imutáveis. O `academic_id` é a referência usada pelos outros serviços, por exemplo `student_id` e `advisor_id` no thesis-service, e por isso é preservado em mudanças de papel e curso.
- Uma mudança de papel ou curso vale nos **novos** tokens. Um orientador rebaixado ou transferido sai de `assignable_advisor_ids` dos coordenadores no próximo login deles.
- O identity-service não consulta os dados dos outros serviços. Vínculos já gravados lá, como um `advisor_id` em uma monografia ou monografias de um estudante transferido de curso, permanecem como estão. A partir do novo token, o escopo de acesso segue o novo papel e curso. Ajustes nesses registros exigem processo próprio em cada serviço.

### Ativação e desativação

`deactivate` marca `is_active=false`. A conta, o histórico e as referências externas são preservados, e `activate` reverte a operação. Repetir a mesma operação devolve 200 sem novo registro de auditoria. Uma conta desativada:

- não obtém novos tokens (401 no login);
- perde o acesso a `/api/auth/me/` e, se for administradora, à administração imediatamente;
- deixa de constar em `assignable_advisor_ids` nos tokens emitidos depois.

### Auditoria administrativa

A tabela `identity_account_audit` recebe uma linha por mudança efetiva, na **mesma transação** da alteração. Uma falha ao gravar a auditoria desfaz a operação.

| Campo | Conteúdo |
| --- | --- |
| `actor_account_id` | Conta administradora responsável. Fica nulo quando a conta foi criada pelo comando confiável `create_academic_user`. |
| `target_account_id` | Conta afetada. É um UUID sem chave estrangeira, para preservar o histórico. |
| `action` | `account.created`, `account.updated`, `account.deactivated` ou `account.activated`. |
| `changes` | Na criação, os dados públicos da conta. Nas demais ações, somente os campos alterados, no formato `{"campo": {"from": ..., "to": ...}}`. Nunca contém senha, hash, token ou chave. |
| `occurred_at` | Instante em UTC. |

O modelo recusa atualização e exclusão de registros, e nenhuma rota HTTP lê ou altera a auditoria. A consulta é feita pelo banco, com acesso administrativo.

### Efeito sobre JWTs já emitidos

- A desativação e as mudanças de papel ou curso valem imediatamente **neste serviço** e em todos os tokens emitidos depois.
- Tokens já emitidos continuam válidos nos outros serviços, como o thesis-service, até `exp`, com as claims antigas. A desativação bloqueia novos logins, mas **não é uma revogação distribuída imediata**.
- A janela de exposição é `IDENTITY_ACCESS_TOKEN_TTL_SECONDS` (padrão 300 s, entre 60 e 3600). Reduza esse valor se precisar de efeito mais rápido.
- Revogação distribuída e refresh tokens serão tratados em etapa própria.

### Exemplos

```powershell
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8002/api/auth/login/ -ContentType application/json -Body (@{ email = "admin@exemplo.edu"; password = Read-Host "Senha" } | ConvertTo-Json)
$auth = @{ Authorization = "Bearer $($login.access_token)" }

Invoke-RestMethod -Uri "http://127.0.0.1:8002/api/users/?role=advisor&is_active=true&search=silva&page=1&page_size=20" -Headers $auth

$novo = @{ name = "Ana Souza"; email = "ana@exemplo.edu"; role = "student"; course_id = "00000000-0000-0000-0000-000000000000"; password = Read-Host "Senha inicial" } | ConvertTo-Json
$conta = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8002/api/users/ -Headers $auth -ContentType application/json -Body $novo

Invoke-RestMethod -Method Patch -Uri "http://127.0.0.1:8002/api/users/$($conta.id)/" -Headers $auth -ContentType application/json -Body (@{ course_id = "11111111-1111-1111-1111-111111111111" } | ConvertTo-Json)
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8002/api/users/$($conta.id)/deactivate/" -Headers $auth
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8002/api/users/$($conta.id)/activate/" -Headers $auth
```

A listagem aceita `role`, `course_id`, `is_active` (`true` ou `false`), `search` (nome ou e-mail, sem diferenciar maiúsculas, até 100 caracteres), `page` e `page_size` (padrão 20, máximo 100). Parâmetros desconhecidos resultam em 400. A resposta contém `results`, `page`, `page_size` e `has_next`, com ordenação estável por e-mail. Filtros e paginação são executados no PostgreSQL.

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

No ambiente Docker local, a chave persistente de desenvolvimento fica em `%USERPROFILE%\.thesis-management\keys\` e é configurada conforme [o guia de infraestrutura](../../infrastructure/README.md#chaves-rsa).

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

A role recebe `CREATEDB` somente para que `python manage.py test` possa criar e remover `test_identity_db` no ambiente local. Ela não é superusuária, não cria roles e não lê tabelas do `thesis_db`. O atributo permite criar bancos novos, mas não dá acesso aos bancos existentes de outras roles.

Fora do desenvolvimento, aplique o menor privilégio:

1. Remova o atributo com `ALTER ROLE identity_user NOCREATEDB`. A API e as migrations não precisam dele, porque a role é dona de `identity_db`.
2. Execute os testes em um pipeline isolado, com uma role própria de teste que tenha `CREATEDB`, ou contra um servidor PostgreSQL descartável.
3. Revogue de `PUBLIC` o `CONNECT` nos bancos dos outros serviços.

Para trocar a senha, use `ALTER ROLE ... PASSWORD` e atualize `IDENTITY_DB_PASSWORD`.

## Docker Compose

Para executar junto com o thesis-service, com confiança JWT configurada, usuários de desenvolvimento e o teste ponta a ponta, siga [o guia de infraestrutura](../../infrastructure/README.md).

Os serviços de identidade ficam em `infrastructure/compose.identity.yaml`, separados do arquivo principal. Os comandos existentes do thesis-service continuam iguais. Para executar apenas o identity, na raiz do repositório:

```sh
docker compose --env-file .env -f infrastructure/compose.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml config --quiet
docker compose --env-file .env -f infrastructure/compose.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml build identity-api
docker compose --env-file .env -f infrastructure/compose.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml up -d --wait identity-api
```

`compose.identity-key.yaml` monta o arquivo indicado em `IDENTITY_JWT_PRIVATE_KEY_HOST_FILE` (caminho absoluto) como secret somente leitura em `/run/secrets/identity_jwt_private_key`. O arquivo precisa estar legível pelo UID 10001. O Compose não recria o contêiner quando apenas o arquivo do secret muda. Nesse caso, use `up -d --no-deps --force-recreate identity-api`. A ordem de inicialização é `identity-db-init`, `identity-migrate` e `identity-api`. A API publica em `127.0.0.1:8002` (`IDENTITY_API_PORT`) e fica saudável quando `/api/auth/me/` responde 401 sem token. Na rede interna do Compose, o endereço é `http://identity-api:8000`. Nenhum volume novo é criado. Para parar só este serviço, use `stop identity-api`.

## Criação de usuários

Há dois caminhos, que usam o mesmo caso de uso e as mesmas validações:

| Caminho | Uso |
| --- | --- |
| `create_academic_user` (CLI) | Operação confiável, com acesso ao servidor. Único meio de criar contas `admin`, inclusive o primeiro administrador. A auditoria registra o ator como nulo. |
| `POST /api/users/` | Administrador ativo autenticado. Cria `student`, `advisor` ou `coordinator`. |

Na CLI, a senha é solicitada duas vezes no terminal ou lida da entrada padrão com `--password-stdin`, e nunca aparece na saída nem nos argumentos. O primeiro administrador precisa de `--course-id` para conseguir token e usar a API:

```powershell
python manage.py create_academic_user --email admin@exemplo.edu --name "Administração" --role admin --course-id 00000000-0000-0000-0000-000000000000
```

Exemplo de conta acadêmica pela CLI:

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

`test_administration` cobre:

- criação autorizada e negada (sem token, por estudante, orientador ou coordenador);
- e-mail duplicado e dados inválidos;
- tentativa de criar administrador;
- filtros, busca e paginação;
- consulta por UUID;
- alterações permitidas e campos imutáveis;
- elevação de privilégio;
- ativação e desativação, inclusive administrador desativado com JWT antigo e papel lido do banco;
- proteção do último administrador;
- rollback e imutabilidade da auditoria;
- efeito das mudanças nos novos tokens.

`test_administration_concurrency` usa `TransactionTestCase` e duas threads com conexões próprias para comprovar a serialização por `SELECT ... FOR UPDATE`, inclusive dois administradores tentando desativar um ao outro.

`identity.tests.test_thesis_compatibility` executa em subprocesso o `AcademicTokenAuthentication` original do thesis-service, com as configurações dele, sobre tokens emitidos pelo login real. O teste confirma a aceitação, os valores da identidade acadêmica e a recusa de uma chave não confiável. Ele é ignorado quando o código do thesis-service não está presente, como dentro da imagem do identity.

## Segurança e limitações

- Não há refresh token nem revogação. Um token continua válido no thesis-service até `exp`, mesmo após desativar a conta ou mudar seu papel. Por isso a duração é curta. A administração deste serviço consulta o banco e não sofre esse atraso.
- A senha inicial é definida pelo administrador. Não há troca obrigatória no primeiro acesso, troca pelo próprio titular nem recuperação. Fora do ambiente local, use HTTPS.
- Administradores só são criados, promovidos ou rebaixados por operação confiável no servidor. A CLI atual cria contas, mas não altera o papel de contas existentes.
- A auditoria administrativa é consultada pelo banco. Não há API de leitura de auditoria.
- Coordenadores e administradores atuam em um único curso por conta. O token para outro curso exige outra conta ou um modelo futuro de vínculos múltiplos.
- O limite de falhas usa `REMOTE_ADDR`. Atrás de um proxy reverso, configure `ALLAUTH_TRUSTED_PROXY_COUNT` ou o cabeçalho confiável do allauth, ou o limite por IP passará a valer para o proxy.
- Logins bem-sucedidos não são limitados nem auditados nesta etapa.
- A configuração local usa HTTP e PostgreSQL e Redis sem TLS. Em implantação, o login exige HTTPS.

## Integração futura

- **thesis-service:** integrado no ambiente Docker local, com a chave pública montada como secret, `THESIS_JWT_ISSUER=urn:tcc:identity` e `THESIS_JWT_AUDIENCE=urn:tcc:api`. O contrato não mudou.
- **Outros serviços:** podem validar o mesmo token com a chave pública. Públicos-alvo por serviço podem ser adotados quando o contrato for estendido.
- **Próximas etapas:** usuários externos temporários, troca de senha pelo titular, recuperação de senha por e-mail, refresh tokens com rotação e revogação, publicação de JWKS para rotação de chaves, auditoria de autenticação e eventos Kafka de ciclo de vida das contas.
