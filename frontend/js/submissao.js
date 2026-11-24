"use strict";

start(async profile => {
  const list = el("div");
  const detail = el("div");
  let page = 1;
  const titleField = value => field("Título", "title", { value, required: true, maxlength: 255 });
  const abstractField = value => field("Resumo", "abstract", { value, type: "textarea" });
  const create = profile.role === "student" ? section("Novo rascunho",
    form([titleField(""), abstractField("")], "Criar rascunho", async data => {
      const work = await api("thesis", thesisPath, { method: "POST", body: {
        ...data, student_id: profile.academic_id, course_id: profile.course_id
      } });
      await load(1);
      await open(work.id);
    }, "Rascunho criado.", true)) : null;

  async function load(current = page) {
    const data = await api("thesis", thesisPath + query({ page: current }));
    page = current;
    list.replaceChildren(section("Trabalhos", results(data.results, work => el("article", { class: "app-row" },
      el("strong", {}, work.title), el("span", { class: "mode-pill" }, label(work.status)),
      button("Detalhes", () => run(() => open(work.id))))), pagination(page, data.has_next, load)));
  }

  async function open(id) {
    const path = recordPath(thesisPath, id);
    const work = await api("thesis", path);
    const draft = work.status === "draft";
    const summary = section(work.title, facts({
      "Situação": label(work.status), "Identificador": work.id, "Curso": work.course_id,
      "Orientador": work.advisor_id || "Aguardando associação", "Resumo": work.abstract,
      "Palavras-chave": work.keywords?.join(", "), "PDF": work.file_sha256 ? "Registrado" : "Pendente"
    }));
    const uploadStatus = el("p", { class: "file-hint" });
    const status = async () => {
      const data = await api("thesis", path + "upload-status/");
      uploadStatus.textContent = "Estado do upload: " + (data.upload_status ? label(data.upload_status) :
        (work.file_sha256 ? "PDF registrado" : "Nenhum upload recente"));
    };
    const mutate = async (method, suffix = "", body) => {
      await api("thesis", path + suffix, { method, body });
      await load();
      if (method === "DELETE") detail.replaceChildren();
      else await open(id);
    };
    summary.append(actions(button("Consultar upload", () => run(status))), uploadStatus);

    if (profile.role === "student" && draft) {
      summary.append(
        form([titleField(work.title), abstractField(work.abstract),
          field("Palavras-chave separadas por vírgulas", "keywords", { value: work.keywords?.join(", ") || "" })],
        "Salvar metadados", data => mutate("PATCH", "", { ...data, keywords: words(data.keywords) }), "Metadados salvos."),
        form([field("PDF de até 20 MiB", "file", { type: "file", required: true, accept: "application/pdf,.pdf" })],
          "Enviar PDF", data => {
            const payload = new FormData();
            payload.append("file", pdf(data.file));
            return mutate("POST", "pdf/", payload);
          }, "PDF enviado."),
        actions(button("Submeter", () => {
          if (confirm("Submeter esta monografia para avaliação do orientador?")) run(() => mutate("POST", "submit/"), "Monografia submetida.");
        }, "success"), button("Excluir rascunho", () => {
          if (confirm("Excluir este rascunho?")) run(() => mutate("DELETE"), "Rascunho excluído.");
        }, "danger")));
    }

    if (profile.role === "coordinator" && draft) {
      const eligible = claims().assignable_advisor_ids || [];
      if (eligible.length) summary.append(form([field("Identificador do orientador elegível", "advisor_id", {
        options: eligible.map(id => [id, id]), value: work.advisor_id && eligible.includes(work.advisor_id) ? work.advisor_id : eligible[0]
      })], "Associar orientador", data => mutate("PATCH", "", data), "Orientador associado."));
      else summary.append(el("p", {}, "Nenhum orientador elegível para esta sessão."));
    }

    if (profile.role === "advisor" && work.status === "submitted") {
      summary.append(actions(...[["approve", "Aprovar submissão", "success"], ["reject", "Rejeitar submissão", "danger"]]
        .map(([route, text, style]) => button(text, () => {
          if (confirm(text + "?")) run(() => mutate("POST", route + "/"), "Decisão registrada.");
        }, style))));
    }

    if (["coordinator", "advisor"].includes(profile.role) && work.status === "advisor_approved") {
      summary.append(actions(link("Propor banca", "banca.html" + query({ thesis: work.id }))));
    }
    if (["coordinator", "admin"].includes(profile.role) && work.status !== "draft") {
      summary.append(actions(link("Preparar publicação", "publicacao.html" + query({ id: work.id }))));
    }
    detail.replaceChildren(summary);
    detail.scrollIntoView({ block: "start" });
  }

  content.replaceChildren(...[create, list, detail].filter(Boolean));
  await load();
  const selected = new URLSearchParams(location.search).get("id");
  if (selected) await open(selected);
});
