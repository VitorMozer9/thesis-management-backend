# Guia de execução e demonstração

Execute os comandos na raiz do clone, salvo indicação de outro diretório. Use exclusivamente arquivos e contas sintéticas na demonstração.

## 1. Preparar o computador

No Windows, instale Git, Python 3.14 e Docker Desktop. Inicie o Docker Desktop com contêineres Linux. Verifique se as portas da tabela do [README](../README.md#execução-local) estão livres.

```powershell
git --version
py -3.14 --version
docker version
docker compose version
docker info --format '{{.OSType}}'
git clone https://github.com/VitorMozer9/thesis-management-backend.git
Set-Location thesis-management-backend
py -3.14 -m venv .venv
$python = '.\.venv\Scripts\python.exe'
& $python -m pip install cryptography==50.0.2
```

No Linux, use Docker Engine com Compose v2, `python3.14 -m venv .venv` e `.venv/bin/python`. Execute o Docker com o usuário autorizado a acessar o daemon. Node.js é opcional para a verificação de sintaxe do frontend.

## 2. Criar a configuração e as chaves

No Windows, em uma instalação nova, prepare o diretório privado do usuário e gere a configuração:

```powershell
$dev = Join-Path $env:USERPROFILE '.thesis-management'
New-Item -ItemType Directory -Force $dev | Out-Null
icacls $dev /inheritance:r /grant:r "${env:USERNAME}:(OI)(CI)F"
& $python infrastructure/setup_dev.py
```

O script copia as opções de `.env.example`, preenche os segredos aleatórios e escreve os caminhos absolutos no novo `.env`. Ele cria um par RSA de 3072 bits em `~/.thesis-management/keys/` ou reutiliza o par que já estiver lá. O Identity monta somente a chave privada de assinatura. Thesis, Defense, Repository e Notification montam a pública para verificação. Mantenha iguais os valores de `IDENTITY_JWT_ISSUER` e `THESIS_JWT_ISSUER`, assim como as duas audiências. Defina `IDENTITY_JWT_PRIVATE_KEY_HOST_FILE` e `THESIS_JWT_PUBLIC_KEY_HOST_FILE` para os arquivos correspondentes se escolher configurar o ambiente manualmente.

No Linux, para Docker padrão sem remapeamento de usuários, prepare a configuração assim:

```sh
.venv/bin/python -m pip install cryptography==50.0.2
.venv/bin/python infrastructure/setup_dev.py
setfacl -m u:10001:r "$HOME/.thesis-management/keys/identity-private.pem"
```

`setfacl` vem do pacote `acl` em distribuições que o separam. O Identity roda com UID 10001 e precisa ler o arquivo montado. Com Docker rootless ou remapeamento, conceda somente leitura ao UID de host correspondente. Mantenha o diretório privado e confira o login após subir a API.

Em um ambiente existente, preserve o `.env` e as chaves. Os arquivos `.env.defense.local`, `.env.repository.local` e `.env.notification.local` dos guias individuais continuam compatíveis. Acrescente os três `--env-file` correspondentes após `--env-file .env` e antes dos overlays, usando somente arquivos que existam. Eles prevalecem sobre a base. Os scripts acadêmicos existentes leem apenas o `.env` e usam a composição Identity/Thesis.

## 3. Subir e verificar os serviços

PowerShell:

```powershell
function dc { docker compose --env-file .env -f infrastructure/compose.yaml -f infrastructure/compose.jwt-file.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml -f infrastructure/compose.defense.yaml -f infrastructure/compose.repository.yaml -f infrastructure/compose.notification.yaml -f infrastructure/compose.frontend.yaml @args }
dc config --quiet
dc config --services
dc build
dc up -d --wait
dc ps -a
```

Bash e shells compatíveis:

```sh
dc() { docker compose --env-file .env -f infrastructure/compose.yaml -f infrastructure/compose.jwt-file.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml -f infrastructure/compose.defense.yaml -f infrastructure/compose.repository.yaml -f infrastructure/compose.notification.yaml -f infrastructure/compose.frontend.yaml "$@"; }
dc config --quiet
dc build
dc up -d --wait
dc ps -a
```

Use sempre o mesmo conjunto de arquivos e o mesmo diretório do projeto. O comando inicializa PostgreSQL, Redis, Kafka e Mailpit, roda a criação de bancos e tópicos, aplica migrations, inicia as cinco APIs, os workers e o Nginx. `identity-migrate`, `thesis-migrate`, `defense-migrate`, `repository-migrate` e `notification-migrate` devem terminar com código zero. O mesmo vale para tarefas de criação de bancos e tópicos. Os serviços contínuos ficam em execução. Alguns workers não declaram healthcheck, então confira os logs.

```powershell
dc logs --tail 50 identity-migrate thesis-migrate defense-migrate repository-migrate notification-migrate
dc logs --tail 50 thesis-outbox-worker thesis-pdf-worker defense-outbox-worker repository-worker repository-publication-outbox notification-kafka notification-delivery
dc exec -T redis redis-cli ping
Invoke-RestMethod http://127.0.0.1:8080/api/repository/
```

Em Linux, use `curl -fsS http://127.0.0.1:8080/api/repository/`. Uma lista vazia é esperada antes da primeira publicação. As APIs protegidas devem retornar 401 sem token. Para uma verificação manual das migrations, rode `dc exec -T thesis-api python manage.py showmigrations` e repita usando o nome das outras APIs.

## 4. Criar contas sintéticas

```powershell
& $python infrastructure/e2e/provision_dev_users.py
```

No Linux, substitua `& $python` por `.venv/bin/python`. O script cria seis contas do mesmo curso e mostra os respectivos UUIDs acadêmicos. Consulte localmente `~/.thesis-management/dev-users.json` para obter as senhas geradas. Proteja esse arquivo e reutilize-o junto com o banco. A variável `THESIS_DEV_USERS_FILE` permite trocar seu caminho. Os scripts usam as portas padrão, ou `IDENTITY_URL` e `THESIS_URL` no caso de `academic_flow.py`.

Abra [o frontend](http://127.0.0.1:8080/) e faça login com o e-mail de uma das contas. Use perfis separados do navegador para manter sessões de papéis diferentes ou saia da conta ao trocar de papel.

## 5. Demonstrar o fluxo completo

1. **Estudante.** Em **Monografias**, crie um rascunho com título e resumo sintéticos. Grave as palavras-chave, envie um PDF textual de até 20 MiB e confira o estado do upload. Anote o UUID da monografia.
2. **Coordenação.** Localize o rascunho e associe o UUID de `dev-advisor` mostrado pelo script ou pelo painel administrativo. Depois, como estudante, submeta a monografia. Ela deve passar para **Submetida**.
3. **Orientador.** Acesse a monografia vinculada e escolha **Aprovar submissão**. Confira também a notificação de submissão no Mailpit em `http://127.0.0.1:8025/`.
4. **Coordenação.** Use **Propor banca** na monografia aprovada ou informe o UUID em **Bancas**. Convide `dev-advisor` como membro interno, usando seu UUID acadêmico. Como orientador, abra a banca e confirme o convite.
5. **Coordenação.** Agende a banca com início futuro, duração mínima de 15 minutos e local ou link HTTPS. Aguarde o término previsto e selecione **Registrar realização**. Como orientador confirmado, registre uma nota de 8, parecer sintético e recomendação **Aprovar**. Consulte o resultado fechado. Para uma apresentação curta, agende a banca antes do horário da sessão.
6. **Coordenação.** Abra **Publicação**. Preencha os metadados da monografia e envie dois documentos PDF distintos: a versão final e um termo de autorização assinado para o cenário sintético, claramente marcado como demonstração. Se houver aprovação com ressalvas, envie o PDF revisado como **PDF corrigido**. A publicação ocorre quando todo o material exigido e a aprovação do Defense estiverem registrados.
7. **Público.** Sem login, abra **Publicados**, pesquise pelo título ou pelas palavras-chave, consulte detalhes e baixe o PDF. Confirme que o termo não aparece no catálogo.
8. **Notificações.** Confira em **Notificações** ou no Mailpit as mensagens de submissão, agendamento e publicação. Os workers processam eventos e SMTP de forma assíncrona. Uma falha de entrega pode ficar pendente para nova tentativa.

Para preparar um PDF textual sintético fora do projeto sem usar um editor, execute:

```powershell
& $python -c "import sys; from pathlib import Path; sys.path.insert(0, 'infrastructure/e2e'); from academic_flow import text_pdf; p=Path.home()/'.thesis-management'/'monografia-demo.pdf'; p.open('xb').write(text_pdf('Monografia sintetica para demonstracao'))"
```

O roteiro pode ser combinado com o script `academic_flow.py`, que cria e aprova uma monografia sintética, verifica permissões, Outbox, extração de PDF e auditoria. Use o UUID que ele retorna e prossiga a partir da etapa de banca. O script mantém a monografia e o PDF de demonstração nos volumes.

```powershell
& $python infrastructure/e2e/academic_flow.py --skip-expiration
```

Para também verificar a expiração natural do JWT com esse script, retire `--skip-expiration`. A espera segue o tempo de vida do token.

### Checklist visual manual

- Abra o login, o painel e o repositório em larguras de desktop e celular. Confira logo, contraste, formulários e navegação sem rolagem horizontal.
- Entre com uma conta de estudante, teste uma senha incorreta, saia e reabra uma página protegida. Confira a solicitação de login após expirar uma sessão.
- Envie um PDF, veja o resultado no formulário e faça uma pesquisa no catálogo. Abra detalhes e download em uma aba sem login.
- Troque para o perfil administrativo e confira se os atalhos mudam. Verifique que uma conta comum não abre a área de usuários.

## 6. Executar testes

Use um ambiente Python 3.14 por serviço para verificar suas dependências sem misturar ambientes. Exemplo no PowerShell, a partir de `services/thesis-service`:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test --keepdb
```

No Linux, use `python3.14` e `.venv/bin/python`. Repita em cada serviço a partir de seu diretório. O usuário PostgreSQL de testes precisa de permissão para criar o banco temporário `test_*`. Use PostgreSQL de desenvolvimento e forneça um usuário de testes autorizado pelas variáveis de banco do serviço. As roles de execução do Defense, Repository e Notification têm privilégios limitados. O Thesis usa `REDIS_TEST_URL`, fixado no banco lógico 15 no Compose. O teste Kafka opcional do Thesis exige um broker de testes e `TEST_KAFKA_BOOTSTRAP_SERVERS`. Prefira um broker descartável para esse teste.

Da raiz, verifique também:

```powershell
dc config --quiet
Get-ChildItem frontend/js/*.js | ForEach-Object { node --check $_.FullName; if ($LASTEXITCODE) { throw "JavaScript inválido" } }
git diff --check
```

## 7. Parar e retomar a pilha

```powershell
dc stop
dc up -d --wait
dc ps
```

Mantenha os volumes, os arquivos de configuração locais, o par de chaves e as credenciais sintéticas. Para investigar uma falha, use `dc logs --tail 100 <serviço>`. Ao alterar código ou dependências, use `dc build <serviço>` e `dc up -d --wait`. Preserve os nomes de projeto e de volumes ao retomar o ambiente.
