"use strict";

const dashboardSize = 5;

function statusChart(rows) {
  const counts = Object.entries(rows.reduce((totals, row) => {
    totals[row.status] = (totals[row.status] || 0) + 1;
    return totals;
  }, {}));
  return el("div", { class: "app-chart" }, el("p", {}, "Situações dos " + rows.length + " registros mais recentes"),
    counts.map(([state, count]) => el("label", {}, label(state) + " · " + count,
      el("meter", { min: 0, max: rows.length, value: count }))));
}

start(async profile => {
  content.replaceChildren(section(profile.name, facts({ "Perfil": roleNames[profile.role], "E-mail": profile.email })));

  async function show(title, service, path, render, href, { byStatus = false, empty } = {}) {
    try {
      const { results: rows } = await api(service, path);
      const panel = section(title, results(rows, render, empty), actions(link("Ver lista completa", href)));
      if (byStatus && rows.length > 1) panel.append(statusChart(rows));
      return panel;
    } catch (error) {
      return section(title, el("p", { class: "notice notice-error" }, error.message), actions(link("Abrir área", href)));
    }
  }

  const work = row => el("article", { class: "app-row" }, link(row.title, "submissao.html" + query({ id: row.id })),
    el("span", { class: "mode-pill" }, label(row.status)));
  const defense = row => el("article", { class: "app-row" },
    link(row.starts_at ? date(row.starts_at) : "Data a definir", "banca.html" + query({ id: row.id })),
    el("span", { class: "mode-pill" }, label(row.status)));
  const account = row => el("article", { class: "app-row" }, el("strong", {}, row.name), el("span", {}, roleNames[row.role]),
    el("span", { class: "mode-pill" }, row.is_active ? "Ativa" : "Inativa"));

  const advisor = profile.role === "advisor";
  const requests = [];
  if (profile.role === "admin") {
    requests.push(show("Usuários recentes", "identity", userPath + query({ page_size: dashboardSize }), account, "usuarios.html"));
  }
  requests.push(show(advisor ? "Submissões aguardando sua avaliação" : "Monografias recentes", "thesis",
    thesisPath + query({ page_size: dashboardSize, status: advisor ? "submitted" : "" }), work,
    "submissao.html", { byStatus: !advisor, empty: advisor ? "Nenhuma submissão aguardando avaliação." : undefined }));
  if (profile.role !== "admin") {
    requests.push(show("Bancas recentes", "defense", defensePath + query({ page_size: dashboardSize }), defense, "banca.html", { byStatus: true }));
  }
  content.append(...await Promise.all(requests));
});
