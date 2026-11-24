"use strict";

start(async profile => {
  const panels = [section(profile.name, facts({ "Perfil": roleNames[profile.role], "E-mail": profile.email }))];
  content.replaceChildren(...panels);

  async function show(title, service, path, render, href, byStatus = false) {
    try {
      const { results: rows } = await api(service, path);
      const panel = section(title, results(rows, render), actions(link("Ver lista completa", href)));
      if (byStatus && rows.length > 1) {
        const counts = Object.entries(rows.reduce((totals, row) => {
          totals[row.status] = (totals[row.status] || 0) + 1;
          return totals;
        }, {}));
        panel.append(el("div", { class: "app-chart" }, el("p", {}, "Situações nesta amostra"),
          counts.map(([state, count]) => el("label", {}, label(state) + " · " + count,
            el("meter", { min: 0, max: rows.length, value: count })))));
      }
      content.append(panel);
    } catch (error) {
      content.append(section(title, el("p", {}, error.message), actions(link("Abrir área", href))));
    }
  }

  const work = row => el("article", { class: "app-row" }, link(row.title, "submissao.html" + query({ id: row.id })),
    el("span", {}, label(row.status)));
  if (profile.role === "admin") {
    await show("Usuários recentes", "identity", userPath + query({ page_size: 5 }),
      row => el("article", { class: "app-row" }, el("strong", {}, row.name), el("span", {}, roleNames[row.role]),
        el("span", {}, row.is_active ? "Ativa" : "Inativa")), "usuarios.html");
  }
  await show(profile.role === "advisor" ? "Submissões para avaliação" : "Monografias recentes",
    "thesis", thesisPath + query({ page_size: 5, status: profile.role === "advisor" ? "submitted" : "" }),
    work, "submissao.html", true);

  if (profile.role !== "admin") await show("Bancas recentes", "defense", defensePath + query({ page_size: 5 }),
    row => el("article", { class: "app-row" }, link(label(row.status), "banca.html" + query({ id: row.id })),
      el("span", {}, date(row.starts_at))), "banca.html", true);
});
