"use strict";

const content = document.querySelector("#content");
const feedback = document.querySelector("#feedback");
const sessionKey = "ufvjm.access";
const returnKey = "ufvjm.return";
const roleNames = { student: "Estudante", advisor: "Orientador", coordinator: "Coordenação", admin: "Administração" };
const labels = {
  draft: "Rascunho", submitted: "Submetida", advisor_approved: "Aprovada pelo orientador",
  advisor_rejected: "Rejeitada pelo orientador", defense_approved: "Aprovada em banca",
  defense_rejected: "Rejeitada em banca", published: "Publicada", proposed: "Proposta",
  awaiting_confirmations: "Aguardando confirmações", scheduled: "Agendada", held: "Realizada",
  cancelled: "Cancelada", pending: "Pendente", confirmed: "Confirmado", declined: "Recusado",
  approved: "Aprovada", approved_with_conditions: "Aprovada com ressalvas", conditional: "Com ressalvas",
  rejected: "Rejeitada", sent: "Enviada", failed: "Falhou", uploading: "Enviando", processing: "Em processamento",
  completed: "Concluído", internal: "Interno", external: "Externo",
  "thesis.submitted": "Monografia submetida", "defense.scheduled": "Banca agendada",
  "defense.cancelled": "Banca cancelada", "repository.published": "Monografia publicada"
};
const fieldNames = {
  title: "Título", abstract: "Resumo", keywords: "Palavras-chave", email: "E-mail", password: "Senha",
  name: "Nome", role: "Papel", course_id: "Curso", academic_id: "Identificador acadêmico",
  advisor_id: "Orientador", student_id: "Estudante", thesis_id: "Monografia", starts_at: "Início",
  ends_at: "Término", venue: "Local", meeting_url: "Link da reunião", grade: "Nota", opinion: "Parecer",
  recommendation: "Recomendação", token: "Código do convite", file: "Arquivo", kind: "Tipo",
  author: "Autor", advisor: "Orientador", reported_year: "Ano da defesa", year: "Ano", search: "Busca"
};
const serverMessages = {
  "This field may not be blank.": "preencha este campo.",
  "This field is required.": "campo obrigatório.",
  "This field may not be null.": "campo obrigatório.",
  "Enter a valid email address.": "informe um e-mail válido.",
  "Must be a valid UUID.": "informe um UUID válido.",
  "A valid integer is required.": "informe um número inteiro.",
  "A valid number is required.": "informe um número válido.",
  "Enter a valid URL.": "informe um endereço válido.",
  "The submitted file is empty.": "o arquivo enviado está vazio.",
  "No file was submitted.": "selecione um arquivo.",
  "At least one field must be provided.": "Altere ao menos um campo.",
  "Abstract is required for submission.": "Informe o resumo antes de submeter.",
  "Keywords are required for submission.": "Informe as palavras-chave antes de submeter.",
  "An advisor must be assigned.": "A coordenação ainda precisa associar um orientador.",
  "A PDF must be attached before submission.": "Envie o PDF antes de submeter.",
  "Only PDF files are allowed.": "Somente arquivos PDF são aceitos.",
  "File does not have a valid PDF signature.": "O arquivo não é um PDF válido.",
  "PDF exceeds the maximum allowed size.": "O PDF excede o tamanho máximo permitido.",
  "Only draft theses can be edited.": "Somente rascunhos podem ser editados.",
  "Only draft theses can be submitted.": "Somente rascunhos podem ser submetidos.",
  "Only draft theses can be deleted.": "Somente rascunhos podem ser excluídos.",
  "Only draft theses can receive PDF uploads.": "Somente rascunhos aceitam envio de PDF.",
  "Only submitted theses can be reviewed by the advisor.": "Somente monografias submetidas podem ser avaliadas.",
  "Only the assigned advisor can review this thesis.": "Somente o orientador associado pode avaliar esta monografia.",
  "The thesis changed or is no longer a draft.": "A monografia foi alterada ou não é mais um rascunho. Recarregue a página.",
  "Email already in use.": "Este e-mail já está em uso.",
  "Email or academic identifier already in use.": "E-mail ou identificador acadêmico já está em uso.",
  "Academic roles other than admin require a course.": "Informe o curso para este papel.",
  "Administrators cannot deactivate their own account.": "Não é possível desativar a própria conta.",
  "The last active administrator cannot be deactivated.": "O último administrador ativo não pode ser desativado.",
  "Account is inactive.": "A conta está inativa.",
  "Account is not linked to an academic course.": "A conta não está vinculada a um curso.",
  "Too many failed login attempts.": "",
  "You do not have permission to perform this action.": "",
  "Not found.": ""
};
const requestTimeout = 30000;
const uploadTimeout = 180000;
const label = value => labels[String(value).toLowerCase()] || value || "—";
const date = value => value ? new Date(value).toLocaleString("pt-BR") : "—";
const query = (params = {}) => {
  const values = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== "" && value != null));
  return values.size ? "?" + values : "";
};
const words = value => value.split(",").map(word => word.trim()).filter(Boolean);
const segment = value => encodeURIComponent(value);
const thesisPath = "/api/theses/";
const defensePath = "/api/defenses/";
const catalogPath = "/api/repository/";
const userPath = "/api/users/";
const notificationPath = "/api/notifications/";
const recordPath = (base, id) => base + segment(id) + "/";


function token() {
  return sessionStorage.getItem(sessionKey);
}

function claims() {
  try {
    const encoded = token().split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(encoded));
  } catch {
    return {};
  }
}

function sessionActive() {
  return Boolean(token()) && claims().exp * 1000 > Date.now();
}

function rememberReturnPage() {
  const page = location.pathname.split("/").pop();
  if (/^[a-z]+\.html$/.test(page) && page !== "index.html") sessionStorage.setItem(returnKey, page + location.search);
}

function takeReturnPage() {
  const page = sessionStorage.getItem(returnKey) || "";
  sessionStorage.removeItem(returnKey);
  return /^[a-z]+\.html(\?[\w=&%.-]*)?$/.test(page) ? page : "painel.html";
}

function signOut(expired = false) {
  sessionStorage.removeItem(sessionKey);
  if (expired) rememberReturnPage();
  else sessionStorage.removeItem(returnKey);
  location.replace(expired ? "index.html?session=expired" : "index.html");
}

function watchExpiration(onExpire) {
  const remaining = claims().exp * 1000 - Date.now();
  if (remaining > 0 && remaining < 2 ** 31 - 1) setTimeout(onExpire, remaining);
}


function apiUrl(service, path) {
  const url = new URL(serviceBases[service].replace(/\/$/, "") + path, location.origin);
  if (!["http:", "https:"].includes(url.protocol)) throw new Error("Endereço de serviço inválido.");
  return url.href;
}

function translateMessage(text) {
  const message = String(text).trim();
  return message in serverMessages ? serverMessages[message] : message;
}

function validationDetails(data, field = "") {
  if (Array.isArray(data)) return data.map(item => validationDetails(item, field)).filter(Boolean).join(" ");
  if (data && typeof data === "object") {
    return Object.entries(data).map(([key, value]) =>
      validationDetails(value, ["detail", "non_field_errors"].includes(key) ? field : key)).filter(Boolean).join(" ");
  }
  if (data == null || data === "") return "";
  const message = translateMessage(data);
  if (!message) return "";
  return (field && fieldNames[field] ? fieldNames[field] + ": " : "") + message;
}

async function readJson(response) {
  if (!response.headers.get("Content-Type")?.includes("application/json")) return null;
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function httpError(response, data) {
  const messages = {
    400: "Confira os dados informados.", 401: "Credenciais inválidas ou sessão expirada.",
    403: "Sua conta não tem permissão para esta operação.", 404: "Registro não encontrado no seu escopo.",
    409: "Operação indisponível no estado atual do registro.", 413: "Arquivo acima do limite aceito.",
    429: "Muitas tentativas. Aguarde antes de tentar novamente.", 503: "Serviço temporariamente indisponível. Tente novamente em instantes."
  };
  const retryAfter = Number(response.headers.get("Retry-After"));
  const detail = [400, 403, 409, 413].includes(response.status) ? validationDetails(data).slice(0, 400) : "";
  const wait = response.status === 429 && retryAfter > 0 ? `Tente novamente em ${Math.ceil(retryAfter)} s.` : "";
  const fallback = response.status >= 500 ? "Falha no serviço. Tente novamente em instantes." : "Não foi possível concluir a operação.";
  const error = new Error([messages[response.status] || fallback, detail, wait].filter(Boolean).join(" "));
  error.status = response.status;
  return error;
}

async function api(service, path, { method = "GET", body, auth = true } = {}) {
  const headers = new Headers({ Accept: "application/json" });
  if (auth) {
    if (!sessionActive()) {
      signOut(Boolean(token()));
      throw new Error("Entre para continuar.");
    }
    headers.set("Authorization", "Bearer " + token());
  }
  const upload = body instanceof FormData;
  if (body !== undefined && !upload) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(apiUrl(service, path), {
      method, headers, body, cache: "no-store", redirect: "error",
      signal: AbortSignal.timeout(upload ? uploadTimeout : requestTimeout)
    });
  } catch (error) {
    if (error.name === "TimeoutError") throw new Error("O serviço demorou para responder. Tente novamente.");
    throw new Error("Não foi possível conectar ao serviço. Verifique sua conexão e tente novamente.");
  }
  if (response.status === 204) return null;
  const data = await readJson(response);
  if (response.ok) return data;
  if (response.status === 401 && auth) signOut(true);
  throw httpError(response, data);
}


function announce(message, kind = "info") {
  feedback.textContent = message;
  feedback.className = "notice notice-" + kind;
  feedback.setAttribute("role", kind === "error" ? "alert" : "status");
  feedback.hidden = !message;
}

async function run(action, message = "") {
  const area = content || document.querySelector("#login-form");
  if (area?.inert) return;
  if (area) {
    area.inert = true;
    area.setAttribute("aria-busy", "true");
  }
  announce("Carregando…");
  try {
    await action();
    announce(message, "success");
  } catch (error) {
    announce(error.message || "Ocorreu um erro.", "error");
  } finally {
    if (area) {
      area.inert = false;
      area.removeAttribute("aria-busy");
    }
  }
}

function confirmed(message, action, success) {
  if (confirm(message)) run(action, success);
}


function el(tag, props = {}, ...children) {
  const element = document.createElement(tag);
  for (const [name, value] of Object.entries(props)) {
    if (name.startsWith("on")) element.addEventListener(name.slice(2), value);
    else if (value !== false && value != null) element.setAttribute(name, value === true ? "" : String(value));
  }
  element.append(...children.flat().filter(value => value != null));
  return element;
}

function button(text, action, variant = "primary", disabled = false) {
  return el("button", { class: "btn btn-" + variant, type: "button", disabled, onclick: action }, text);
}

function link(text, href) {
  return el("a", { class: "subtle-link", href }, text);
}

function actions(...children) {
  return el("div", { class: "app-actions" }, ...children);
}

function hint(text) {
  return el("p", { class: "file-hint" }, text);
}

function field(text, name, { type = "text", value = "", options, help, ...attributes } = {}) {
  let input;
  if (options) {
    input = el("select", { name, ...attributes }, options.map(([key, title]) => el("option", { value: key }, title)));
    input.value = value ?? options[0][0];
    if (input.selectedIndex < 0) input.value = options[0][0];
  } else if (type === "textarea") {
    input = el("textarea", { name, rows: 4, ...attributes }, value ?? "");
  } else {
    input = el("input", { name, type, value: value ?? "", ...attributes });
  }
  return el("label", { class: "field" }, el("span", {}, text), input, help ? el("small", {}, help) : null);
}

function form(fields, text, handler, success = "", { reset = false, confirmation = "" } = {}) {
  return el("form", { class: "app-form", method: "post", onsubmit: event => {
    event.preventDefault();
    const target = event.currentTarget;
    if (confirmation && !confirm(confirmation)) return;
    const data = Object.fromEntries(new FormData(target));
    run(async () => {
      await handler(data);
      if (reset) target.reset();
    }, success);
  } }, el("div", { class: "submission-grid" }, fields), el("button", { class: "btn btn-primary", type: "submit" }, text));
}

function section(title, ...items) {
  return el("section", { class: "app-panel info-section" }, el("h2", {}, title), ...items);
}

function facts(values) {
  return el("dl", { class: "app-facts" }, Object.entries(values).flatMap(([key, value]) =>
    [el("dt", {}, key), el("dd", {}, value || "—")]));
}

function pagination(page, hasNext, load) {
  if (page <= 1 && !hasNext) return null;
  return el("nav", { class: "app-actions pagination", "aria-label": "Paginação" },
    button("Anterior", () => run(() => load(page - 1)), "secondary", page <= 1),
    el("span", { "aria-current": "page" }, "Página " + page),
    button("Próxima", () => run(() => load(page + 1)), "secondary", !hasNext));
}

function results(rows, render, empty = "Nenhum registro encontrado.") {
  return rows.length ? el("div", { class: "app-list" }, rows.map(render)) : el("p", { class: "empty-state" }, empty);
}

function reveal(element) {
  element.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
}

function pdf(file) {
  if (!(file instanceof File) || !file.size) throw new Error("Selecione um arquivo PDF.");
  if (!/\.pdf$/i.test(file.name)) throw new Error("O arquivo precisa estar no formato PDF.");
  if (file.size > 20 * 1024 * 1024) throw new Error("O PDF deve ter até 20 MiB.");
  return file;
}


function navigation(profile) {
  const nav = document.querySelector("#navigation");
  if (!nav) return;
  const links = [link("Publicados", "publicados.html")];
  if (profile) {
    links.push(link("Painel", "painel.html"), link("Monografias", "submissao.html"));
    if (profile.role !== "admin") links.push(link("Bancas", "banca.html"));
    if (profile.role === "admin") links.push(link("Usuários", "usuarios.html"));
    if (["admin", "coordinator"].includes(profile.role)) links.push(link("Publicação", "publicacao.html"));
    links.push(link("Notificações", "notificacoes.html"), button("Sair", () => signOut()));
  } else links.push(link("Entrar", "index.html"));
  for (const item of links) {
    if (item.href === location.origin + location.pathname) item.setAttribute("aria-current", "page");
  }
  nav.replaceChildren(...links);
}

function start(render, { roles, publicPage = false } = {}) {
  run(async () => {
    let profile = null;
    if (publicPage) {
      if (sessionActive()) {
        navigation({ role: claims().role });
        watchExpiration(() => {
          sessionStorage.removeItem(sessionKey);
          navigation(null);
        });
      } else sessionStorage.removeItem(sessionKey);
    } else {
      profile = await api("identity", "/api/auth/me/");
      navigation(profile);
      watchExpiration(() => signOut(true));
      if (roles && !roles.includes(profile.role)) throw new Error("Esta área não está disponível para seu perfil.");
    }
    await render(profile);
  });
}
