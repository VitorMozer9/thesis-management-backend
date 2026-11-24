"use strict";

const academicRoles = [["student", "Estudante"], ["advisor", "Orientador"], ["coordinator", "Coordenação"]];

function profileFields(row) {
  return [
    field("Nome", "name", { value: row.name, required: true, maxlength: 150 }),
    field("E-mail", "email", { value: row.email, type: "email", required: true, maxlength: 254 }),
    ...(row.role === "admin" ? [] : [field("Papel", "role", { value: row.role, options: academicRoles })]),
    field("UUID do curso", "course_id", { value: row.course_id, required: row.role !== "admin" })
  ];
}

function accountChanges(row, data) {
  const values = { ...data, name: data.name.trim(), email: data.email.trim(), course_id: data.course_id.trim() || null };
  return Object.fromEntries(Object.entries(values).filter(([key, value]) => value !== row[key]));
}

start(async profile => {
  const list = el("div");
  const detail = el("div");
  let page = 1;
  let filters = {};

  async function load(current = page) {
    const data = await api("identity", userPath + query({ ...filters, page: current }));
    page = current;
    list.replaceChildren(section("Contas", results(data.results, row => el("article", { class: "app-row" },
      el("strong", {}, row.name), el("span", { class: "row-meta" }, row.email), el("span", {}, roleNames[row.role]),
      el("span", { class: "mode-pill" + (row.is_active ? "" : " is-inactive") }, row.is_active ? "Ativa" : "Inativa"),
      button("Detalhes", () => run(() => open(row.id)), "secondary"))), pagination(page, data.has_next, load)));
  }

  function activationButton(row, path, id) {
    const active = row.is_active;
    return actions(button(active ? "Desativar conta" : "Ativar conta", () => confirmed(
      active ? "Desativar esta conta? O usuário não conseguirá mais entrar." : "Ativar esta conta?", async () => {
        await api("identity", path + (active ? "deactivate/" : "activate/"), { method: "POST" });
        await load();
        await open(id);
      }, "Situação atualizada."), active ? "danger" : "success"));
  }

  async function open(id) {
    const path = recordPath(userPath, id);
    const row = await api("identity", path);
    const panel = section(row.name, facts({
      "E-mail": row.email, "Papel": roleNames[row.role], "Curso": row.course_id,
      "Identificador acadêmico": row.academic_id, "Situação": row.is_active ? "Ativa" : "Inativa"
    }));
    panel.append(el("div", { class: "subsection" }, el("h3", {}, "Editar conta"),
      form(profileFields(row), "Salvar alterações", async data => {
        const changes = accountChanges(row, data);
        if (!Object.keys(changes).length) throw new Error("Nenhuma alteração para salvar.");
        await api("identity", path, { method: "PATCH", body: changes });
        await load();
        await open(id);
      }, "Conta atualizada.")));
    if (id !== profile.id) panel.append(activationButton(row, path, id));
    detail.replaceChildren(panel);
    reveal(detail);
  }

  content.replaceChildren(
    section("Cadastrar usuário acadêmico", form([...profileFields({}),
      field("UUID acadêmico, se já atribuído", "academic_id"),
      field("Senha inicial", "password", { type: "password", required: true, minlength: 12, autocomplete: "new-password",
        help: "Mínimo de 12 caracteres; evite senhas comuns ou apenas numéricas." })
    ], "Cadastrar", async data => {
      content.querySelector('input[name="password"]').value = "";
      const body = { ...data, name: data.name.trim(), email: data.email.trim(), course_id: data.course_id.trim(),
        academic_id: data.academic_id.trim() || null };
      const created = await api("identity", userPath, { method: "POST", body });
      await load(1);
      await open(created.id);
    }, "Conta cadastrada.", { reset: true })),
    section("Buscar usuários", form([
      field("Nome ou e-mail", "search", { maxlength: 100 }),
      field("Papel", "role", { options: [["", "Todos"], ...academicRoles, ["admin", "Administração"]] }),
      field("Situação", "is_active", { options: [["", "Todas"], ["true", "Ativas"], ["false", "Inativas"]] })
    ], "Buscar", async data => {
      filters = { search: data.search.trim(), role: data.role, is_active: data.is_active };
      await load(1);
    })), list, detail);
  await load(1);
}, { roles: ["admin"] });
