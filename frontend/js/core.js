"use strict";

const content = document.querySelector("#content");
const feedback = document.querySelector("#feedback");
const sessionKey = "ufvjm.access";
const roleNames = { student: "Estudante", advisor: "Orientador", coordinator: "Coordenação", admin: "Administração" };
const labels = {
  draft: "Rascunho", submitted: "Submetida", advisor_approved: "Aprovada pelo orientador",
  advisor_rejected: "Rejeitada pelo orientador", defense_approved: "Aprovada em banca",
  defense_rejected: "Rejeitada em banca", published: "Publicada", proposed: "Proposta",
  awaiting_confirmations: "Aguardando confirmações", scheduled: "Agendada", held: "Realizada",
  cancelled: "Cancelada", pending: "Pendente", confirmed: "Confirmado", declined: "Recusado",
  approved: "Aprovada", approved_with_conditions: "Aprovada com ressalvas", conditional: "Com ressalvas",
  rejected: "Rejeitada", sent: "Enviada", failed: "Falhou", uploading: "Enviando", completed: "Concluído"
};
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

function signOut(expired = false) {
  sessionStorage.removeItem(sessionKey);
  location.replace(expired ? "index.html?session=expired" : "index.html");
}

function apiUrl(service, path) {
  const url = new URL(serviceBases[service].replace(/\/$/, "") + path, location.origin);
  if (!["http:", "https:"].includes(url.protocol)) throw new Error("Endereço de serviço inválido.");
  return url.href;
}

function validationDetails(data) {
  if (typeof data === "string") return data.slice(0, 300);
  if (data && typeof data === "object") return Object.values(data).flatMap(validationDetails).join(" ").slice(0, 300);
  return "";
}

async function api(service, path, { method = "GET", body, auth = true } = {}) {
  const headers = new Headers({ Accept: "application/json" });
  if (auth) {
    if (!token() || !(claims().exp * 1000 > Date.now())) {
      signOut(Boolean(token()));
      throw new Error("Entre para continuar.");
    }
    headers.set("Authorization", "Bearer " + token());
  }
  if (body !== undefined && !(body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(apiUrl(service, path), { method, headers, body, cache: "no-store", redirect: "error" });
  } catch {
    throw new Error("Não foi possível conectar ao serviço. Tente novamente.");
  }
  if (response.status === 204) return null;
  const data = response.headers.get("Content-Type")?.includes("application/json") ? await response.json() : null;
  if (response.ok) return data;
  if (response.status === 401 && auth) signOut(true);
  const messages = {
    400: "Confira os dados informados.", 401: "Credenciais inválidas ou sessão expirada.",
    403: "Sua conta não tem permissão para esta operação.", 404: "Registro não encontrado no seu escopo.",
    409: "Operação indisponível no estado atual do registro.", 413: "Arquivo acima do limite aceito.",
    429: "Muitas tentativas. Aguarde antes de tentar novamente.", 503: "Serviço temporariamente indisponível."
  };
  const detail = [400, 409].includes(response.status) ? validationDetails(data) : "";
  const error = new Error([messages[response.status] || "Não foi possível concluir a operação.", detail].filter(Boolean).join(" "));
  error.status = response.status;
  throw error;
}

function announce(message, kind = "info") {
  feedback.textContent = message;
  feedback.className = "notice notice-" + kind;
  feedback.hidden = !message;
}

async function run(action, message = "") {
  const area = content || document.querySelector("#login-form");
  if (area?.inert) return;
  if (area) area.inert = true;
  announce("Carregando…");
  try {
    await action();
    announce(message, "success");
  } catch (error) {
    announce(error.message || "Ocorreu um erro.", "error");
  } finally {
    if (area) area.inert = false;
  }
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

function field(text, name, { type = "text", value = "", options, ...attributes } = {}) {
  let input;
  if (options) {
    input = el("select", { name, ...attributes }, options.map(([key, title]) => el("option", { value: key }, title)));
    input.value = value || options[0][0];
  } else if (type === "textarea") {
    input = el("textarea", { name, rows: 4, ...attributes }, value);
  } else {
    input = el("input", { name, type, value, ...attributes });
  }
  return el("label", { class: "field" }, el("span", {}, text), input);
}

function form(fields, text, handler, success = "", resetOnSuccess = false) {
  return el("form", { class: "app-form", method: "post", onsubmit: event => {
    event.preventDefault();
    const target = event.currentTarget;
    const data = Object.fromEntries(new FormData(target));
    run(async () => {
      await handler(data);
      if (resetOnSuccess) target.reset();
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
  return actions(button("Anterior", () => run(() => load(page - 1)), "primary", page <= 1),
    el("span", {}, "Página " + page), button("Próxima", () => run(() => load(page + 1)), "primary", !hasNext));
}

function results(rows, render) {
  return rows.length ? el("div", { class: "app-list" }, rows.map(render)) :
    el("p", { class: "empty-state" }, "Nenhum registro encontrado.");
}

function pdf(file) {
  if (!(file instanceof File) || !file.size || !/\.pdf$/i.test(file.name) || file.size > 20 * 1024 * 1024) {
    throw new Error("Selecione um PDF de até 20 MiB.");
  }
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
      if (token() && claims().exp * 1000 > Date.now()) navigation({ role: claims().role });
    } else {
      profile = await api("identity", "/api/auth/me/");
      navigation(profile);
      if (roles && !roles.includes(profile.role)) throw new Error("Esta área não está disponível para seu perfil.");
    }
    await render(profile);
  });
}
