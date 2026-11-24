"use strict";

const searchSchema = [
  ["Título", "title", { maxlength: 255 }],
  ["Autor", "author", { maxlength: 200 }],
  ["Orientador", "advisor", { maxlength: 200, help: "Nome completo, exatamente como publicado." }],
  ["UUID do curso", "course_id", { maxlength: 36 }],
  ["Ano da defesa", "year", { type: "number", min: 1900, max: 9999 }],
  ["Palavras-chave", "keywords", { maxlength: 200 }]
];

function downloadLink(id) {
  return el("a", { class: "btn btn-secondary", href: apiUrl("repository", recordPath(catalogPath, id) + "pdf/"), download: "" }, "Baixar PDF");
}

start(async () => {
  let filters = {};
  const list = el("div", { class: "results-area" });
  const detail = el("div");
  const search = form(searchSchema.map(([text, key, options]) => field(text, key, options)), "Buscar", async data => {
    filters = Object.fromEntries(Object.entries(data).map(([key, value]) => [key, value.trim()]));
    await load(1);
  });
  search.append(button("Limpar filtros", () => run(async () => {
    search.reset();
    filters = {};
    await load(1);
  }), "secondary"));

  function showDetail(row) {
    detail.replaceChildren(section(row.title, facts({
      "Autor": row.author, "Orientador": row.advisor, "Curso": row.course_id, "Ano da defesa": String(row.defense_year ?? ""),
      "Resultado": label(row.result), "Palavras-chave": row.keywords.join(", "), "Publicação": date(row.published_at)
    }), actions(downloadLink(row.thesis_id))));
    reveal(detail);
  }

  function card(row, index) {
    return el("article", { class: "thesis-card" },
      el("img", { class: "thesis-cover", src: "assets/capa-" + (index % 3 + 1) + ".jpg", alt: "", loading: "lazy" }),
      el("div", { class: "thesis-card-body" }, el("h2", { class: "thesis-card-title" }, row.title),
        el("p", { class: "author-inline" }, row.author),
        el("p", { class: "thesis-meta" }, [row.advisor, row.defense_year].filter(Boolean).join(" · ")),
        actions(button("Detalhes", () => showDetail(row)), downloadLink(row.thesis_id))));
  }

  async function load(page) {
    const data = await api("repository", catalogPath + query({ ...filters, page }), { auth: false });
    detail.replaceChildren();
    const filtered = Object.values(filters).some(Boolean);
    list.replaceChildren(el("div", { class: "thesis-list" }, data.results.length ? data.results.map(card) :
      el("p", { class: "empty-state" }, filtered ? "Nenhuma publicação corresponde aos filtros." : "Ainda não há monografias publicadas.")),
    pagination(page, data.has_next, async next => {
      await load(next);
      reveal(list);
    }) || "");
  }

  content.replaceChildren(section("Pesquisar publicações", search), detail, list);
  await load(1);
  const selected = new URLSearchParams(location.search).get("id");
  if (selected) showDetail(await api("repository", recordPath(catalogPath, selected), { auth: false }));
}, { publicPage: true });
