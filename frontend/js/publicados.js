"use strict";

start(async () => {
  let filters = {};
  const list = el("div", { class: "results-area" });
  const detail = el("div");
  const schema = [["Título", "title", 255], ["Autor", "author", 200], ["Orientador", "advisor", 200],
    ["UUID do curso", "course_id", 36], ["Ano da defesa", "year"], ["Palavras-chave", "keywords", 200]];
  const search = form(schema.map(([name, key, max]) => field(name, key, key === "year" ?
    { type: "number", min: 1900, max: 9999 } : { maxlength: max })), "Buscar", async data => {
    filters = Object.fromEntries(Object.entries(data).map(([key, value]) => [key, value.trim()]));
    await load(1);
  });
  search.append(button("Limpar filtros", () => run(async () => {
    search.reset();
    filters = {};
    await load(1);
  })));

  function download(id) {
    return link("Baixar PDF", apiUrl("repository", recordPath(catalogPath, id) + "pdf/"));
  }

  async function open(id) {
    const row = await api("repository", recordPath(catalogPath, id), { auth: false });
    detail.replaceChildren(section(row.title, facts({
      "Autor": row.author, "Orientador": row.advisor, "Curso": row.course_id, "Ano da defesa": row.defense_year,
      "Resultado": label(row.result), "Palavras-chave": row.keywords.join(", "), "Publicação": date(row.published_at)
    }), actions(download(id))));
    detail.scrollIntoView({ block: "start" });
  }

  async function load(page) {
    const data = await api("repository", catalogPath + query({ ...filters, page }), { auth: false });
    detail.replaceChildren();
    list.replaceChildren(results(data.results, (row, index) => el("article", { class: "thesis-card" },
      el("img", { class: "thesis-cover", src: "assets/capa-" + (index % 3 + 1) + ".jpg", alt: "", loading: "lazy" }),
      el("div", { class: "thesis-card-body" }, el("h2", { class: "thesis-card-title" }, row.title),
        el("p", { class: "author-inline" }, row.author),
        el("p", { class: "thesis-meta" }, row.advisor + " · " + row.defense_year),
        actions(button("Detalhes", () => run(() => open(row.thesis_id))), download(row.thesis_id))))),
    pagination(page, data.has_next, load));
  }

  content.replaceChildren(section("Pesquisar publicações", search), detail, list);
  await load(1);
}, { publicPage: true });
