"use strict";

start(async profile => {
  const list = el("div");
  const detail = el("div");
  const roles = [["student", "Estudante"], ["advisor", "Orientador"], ["coordinator", "Coordenação"]];
  const profileFields = row => [
    field("Nome", "name", { value: row.name, required: true, maxlength: 200 }),
    field("E-mail", "email", { value: row.email, type: "email", required: true, maxlength: 254 }),
    ...(row.role === "admin" ? [] : [field("Papel", "role", { value: row.role, options: roles })]),
    field("UUID do curso", "course_id", { value: row.course_id, required: row.role !== "admin" })
  ];
  let page = 1;
  let search = "";

  async function load(current = page) {
    const data = await api("identity", userPath + query({ page: current, search }));
    page = current;
    list.replaceChildren(section("Contas", results(data.results, row => el("article", { class: "app-row" },
      el("strong", {}, row.name), el("span", {}, roleNames[row.role]),
      el("span", {}, row.is_active ? "Ativa" : "Inativa"),
      button("Detalhes", () => run(() => open(row.id))))), pagination(page, data.has_next, load)));
  }

  async function open(id) {
    const path = recordPath(userPath, id);
    const row = await api("identity", path);
    const panel = section(row.name, facts({
      "E-mail": row.email, "Papel": roleNames[row.role], "Curso": row.course_id,
      "Identificador acadêmico": row.academic_id, "Situação": row.is_active ? "Ativa" : "Inativa"
    }));
    panel.append(form(profileFields(row), "Salvar alterações", async data => {
        const values = { ...data, course_id: data.course_id || null };
        const changes = Object.fromEntries(Object.entries(values).filter(([key, value]) => value !== row[key]));
        if (!Object.keys(changes).length) return;
        await api("identity", path, { method: "PATCH", body: changes });
        await load();
        await open(id);
    }, "Conta atualizada."));
    if (id !== profile.id) {
      panel.append(actions(button(row.is_active ? "Desativar conta" : "Ativar conta", () => {
        const route = row.is_active ? "deactivate/" : "activate/";
        if (confirm(row.is_active ? "Desativar esta conta?" : "Ativar esta conta?")) run(async () => {
          await api("identity", path + route, { method: "POST" });
          await load();
          await open(id);
        }, "Situação atualizada.");
      }, row.is_active ? "danger" : "success")));
    }
    detail.replaceChildren(panel);
    detail.scrollIntoView({ block: "start" });
  }

  content.replaceChildren(
    section("Cadastrar usuário acadêmico", form([...profileFields({}),
      field("UUID acadêmico, se já atribuído", "academic_id"),
      field("Senha inicial", "password", { type: "password", required: true, autocomplete: "new-password" })
    ], "Cadastrar", async data => {
      content.querySelector('input[name="password"]').value = "";
      const created = await api("identity", userPath, { method: "POST", body: { ...data, academic_id: data.academic_id || null } });
      await load(1);
      await open(created.id);
    }, "Conta cadastrada.", true)),
    section("Buscar usuários", form([field("Nome ou e-mail", "search", { maxlength: 100 })], "Buscar", async data => {
      search = data.search.trim();
      await load(1);
    })), list, detail);
  await load(1);
}, { roles: ["admin"] });
