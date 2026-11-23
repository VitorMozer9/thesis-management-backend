# Contrato de identidade do serviço de monografias

O futuro `identity-service` autentica a conta e assina tokens de acesso. O cliente envia o token no cabeçalho `Authorization: Bearer <token>`. Em implantação, o transporte deve usar HTTPS. O serviço verifica o token localmente e cria uma identidade acadêmica imutável para a requisição.

## Configuração de confiança

Instale as dependências com `python -m pip install -r requirements.txt`. Forneça as três variáveis por um canal de configuração confiável.

| Variável | Valor esperado |
| --- | --- |
| `THESIS_JWT_PUBLIC_KEY` | Chave pública RSA em PEM, com pelo menos 2048 bits. Aceita quebras de linha reais ou representadas por `\n`. |
| `THESIS_JWT_ISSUER` | Identificador exato do emissor confiável. |
| `THESIS_JWT_AUDIENCE` | Identificador exato do público desta API. |

O verificador exige assinatura RS256 e cabeçalho JOSE com `typ=at+jwt`. Configuração ausente impede a autenticação. Cada instância confia em uma chave pública configurada localmente. A rotação exige substituição coordenada e reinício. A chave privada fica com o emissor.

## Claims assinadas

| Claim | Significado |
| --- | --- |
| `iss`, `aud` | Emissor configurado e público-alvo como uma única string. |
| `iat`, `exp` | Instantes de emissão e expiração em segundos inteiros desde a época Unix. O serviço rejeita emissão futura ou token expirado e verifica `nbf` quando presente. |
| `sub` | UUID da conta. |
| `academic_id` | UUID acadêmico verificado para o papel do ator. Pode ser diferente de `sub`. |
| `role` | Um dos valores `student`, `advisor`, `coordinator` ou `admin`. |
| `course_id` | UUID de um curso autorizado para este token. |
| `assignable_advisor_ids` | Lista opcional de UUIDs dos orientadores elegíveis para o curso. O padrão é uma lista vazia. Somente a coordenação usa essa permissão. |

Antes de emitir o token, o provedor deve verificar o vínculo entre conta e identidade acadêmica, o papel, o curso e a elegibilidade dos orientadores. Para atuar em outro curso, a pessoa precisa de um token para esse curso. O contrato prevê tokens de curta duração. As permissões assinadas podem continuar válidas até a expiração ou substituição da chave. A implementação atual dispensa consultas de revogação e ignora fontes de chaves indicadas pelo cliente.

## Política de acesso

Todas as leituras, inclusive a do estado de upload, são restritas ao curso assinado. O estudante vê as próprias monografias e o orientador vê aquelas que orienta. Coordenação e administração têm leitura no curso. Filtros do cliente restringem ainda mais o resultado antes da paginação.

| Rota | Quem pode acessar |
| --- | --- |
| `GET /api/theses/` | Lista no escopo do ator. Aceita `student_id`, `advisor_id`, `course_id`, `status`, `search`, `page` e `page_size`. Retorna `results` e `has_next`. |
| `GET /api/theses/{id}/` e `GET /api/theses/{id}/upload-status/` | Leitura no mesmo escopo. |
| `POST /api/theses/` | Estudante. Os campos obrigatórios `student_id` e `course_id` devem coincidir com os valores assinados. |
| `PATCH /api/theses/{id}/` | Estudante titular edita metadados do rascunho. Coordenador pode enviar exclusivamente `advisor_id` de um orientador elegível para o curso. |
| `POST /api/theses/{id}/pdf/`, `POST /api/theses/{id}/submit/` e `DELETE /api/theses/{id}/` | Estudante titular, em rascunho. A submissão também exige resumo, palavras-chave, orientador e PDF. |
| `POST /api/theses/{id}/approve/` e `POST /api/theses/{id}/reject/` | Orientador vinculado, monografia submetida e corpo vazio. |

Credencial ausente ou inválida resulta em HTTP 401. Uma operação proibida para o papel resulta em 403. Uma consulta a recurso inexistente ou fora do escopo retorna 404. Transições inválidas e conflitos de escrita retornam 409.
