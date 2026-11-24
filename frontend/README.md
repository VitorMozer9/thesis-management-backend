# UFVJM TCCs

Interface em HTML, CSS e JavaScript com as APIs de identidade, monografias, bancas, repositório e notificações. O endereço local padrão é `http://127.0.0.1:8080`. A sessão fica restrita à aba, no `sessionStorage`, e expira conforme o JWT. A aplicação renderiza dados externos como texto e o Nginx aplica uma política de scripts e conexões restrita à mesma origem.

## Execução

Prepare os arquivos `.env`, `.env.defense.local`, `.env.repository.local` e `.env.notification.local` conforme os READMEs dos serviços. Na raiz do projeto, execute:

```sh
docker compose --env-file .env --env-file .env.defense.local --env-file .env.repository.local --env-file .env.notification.local -f infrastructure/compose.yaml -f infrastructure/compose.jwt-file.yaml -f infrastructure/compose.identity.yaml -f infrastructure/compose.identity-key.yaml -f infrastructure/compose.defense.yaml -f infrastructure/compose.repository.yaml -f infrastructure/compose.notification.yaml -f infrastructure/compose.frontend.yaml up -d --build --wait frontend identity-api thesis-api thesis-outbox-worker thesis-pdf-worker defense-api defense-outbox-worker repository-api repository-worker repository-publication-outbox notification-api notification-kafka notification-delivery
```

Abra `http://127.0.0.1:8080` e use uma conta acadêmica de desenvolvimento. O catálogo público também está em `/publicados.html`. Para mudar a porta publicada, defina `FRONTEND_PORT`. O Nginx encaminha somente as famílias públicas de rotas `/api/` e aceita corpos multipart de até 21 MiB para PDFs de até 20 MiB. `js/config.js` define as bases por serviço. O Compose usa a mesma origem e os nomes internos da rede. Alterar para outra origem exige ajustar a política de conteúdo e o CORS apenas para origens autorizadas.

## Limites dos contratos

A seleção de orientadores usa a lista de UUIDs elegíveis do token da coordenação. O contrato não fornece à coordenação um diretório com nomes de orientadores ou membros internos. O catálogo identifica cursos por UUID. O serviço de monografias permite enviar o PDF e consultar seu estado, enquanto o download disponível pela API é o da versão pública no Repository. O dashboard usa apenas os registros da primeira página consultada em cada serviço. A compatibilidade das respostas do backend permite consultar as palavras-chave salvas na monografia.

## Testes

Os testes de regressão usam apenas o Node.js 20 ou superior, sem dependências: `node --test frontend/tests/regression.test.mjs`.
