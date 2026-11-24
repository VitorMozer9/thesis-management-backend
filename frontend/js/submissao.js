"use strict";

const thesisStatuses = ["draft", "submitted", "advisor_approved", "advisor_rejected", "defense_approved", "defense_rejected", "published"];

function submissionRequirements(work) {
  return [
    ["Resumo preenchido", Boolean(work.abstract?.trim())],
    ["Palavras-chave informadas", Boolean(work.keywords?.length)],
    ["Orientador associado pela coordenação", Boolean(work.advisor_id)],
    ["PDF enviado", Boolean(work.file_key && work.file_sha256)]
  ];
}

function requirementList(requirements) {
  return el("ul", { class: "checklist", "aria-label": "Requisitos para submissão" }, requirements.map(([text, done]) =>
    el("li", { class: done ? "is-done" : "is-missing" }, el("span", { "aria-hidden": "true" }, done ? "✓" : "•"),
      text + (done ? "" : " (pendente)"))));
}

start(async profile => {
  const list = el("div");
  const detail = el("div");
  let page = 1;
  let filters = {};
  const titleField = value => field("Título", "title", { value, required: true, maxlength: 255 });
  const abstractField = value => field("Resumo", "abstract", { value, type: "textarea" });
  const create = profile.role === "student" ? section("Novo rascunho",
    form([titleField(""), abstractField("")], "Criar rascunho", async data => {
      const work = await api("thesis", thesisPath, { method: "POST", body: {
        ...data, title: data.title.trim(), student_id: profile.academic_id, course_id: profile.course_id
      } });
      await load(1);
      await open(work.id);
    }, "Rascunho criado.", { reset: true })) : null;

  const search = section("Filtrar trabalhos", form([
    field("Título ou termo", "search", { maxlength: 255 }),
    field("Situação", "status", { options: [["", "Todas"], ...thesisStatuses.map(status => [status, label(status)])] })
  ], "Filtrar", async data => {
    filters = { search: data.search.trim(), status: data.status };
    await load(1);
  }));

  async function load(current = page) {
    const data = await api("thesis", thesisPath + query({ ...filters, page: current }));
    page = current;
    list.replaceChildren(section("Trabalhos", results(data.results, work => el("article", { class: "app-row" },
      el("strong", {}, work.title), el("span", { class: "mode-pill" }, label(work.status)),
      button("Detalhes", () => run(() => open(work.id)), "secondary"))), pagination(page, data.has_next, load)));
  }

  function studentDraftPanels(work, mutate) {
    const requirements = submissionRequirements(work);
    const ready = requirements.every(([, done]) => done);
    return [
      el("div", { class: "subsection" }, el("h3", {}, "Metadados"),
        form([titleField(work.title), abstractField(work.abstract),
          field("Palavras-chave separadas por vírgulas", "keywords", { value: work.keywords?.join(", ") || "" })],
        "Salvar metadados", data => mutate("PATCH", "", { title: data.title.trim(), abstract: data.abstract, keywords: words(data.keywords) }),
        "Metadados salvos.")),
      el("div", { class: "subsection" }, el("h3", {}, "Arquivo PDF"),
        form([field("PDF de até 20 MiB", "file", { type: "file", required: true, accept: "application/pdf,.pdf",
          help: work.file_sha256 ? "Um novo envio substitui o PDF registrado." : "" })],
        "Enviar PDF", data => {
          const payload = new FormData();
          payload.append("file", pdf(data.file));
          return mutate("POST", "pdf/", payload);
        }, "PDF enviado.")),
      el("div", { class: "subsection" }, el("h3", {}, "Submissão"), requirementList(requirements),
        actions(
          button("Submeter para o orientador", () => confirmed("Submeter esta monografia? Após a submissão, ela não poderá ser editada.",
            () => mutate("POST", "submit/"), "Monografia submetida."), "success", !ready),
          button("Excluir rascunho", () => confirmed("Excluir este rascunho? A operação não pode ser desfeita.",
            () => mutate("DELETE"), "Rascunho excluído."), "danger")))
    ];
  }

  function coordinatorPanel(work, mutate) {
    const eligible = claims().assignable_advisor_ids || [];
    if (!eligible.length) return el("p", { class: "file-hint" }, "Nenhum orientador elegível para esta sessão.");
    return el("div", { class: "subsection" }, el("h3", {}, "Orientação"), form([field("Identificador do orientador elegível", "advisor_id", {
      options: eligible.map(id => [id, id]), value: work.advisor_id && eligible.includes(work.advisor_id) ? work.advisor_id : eligible[0]
    })], work.advisor_id ? "Alterar orientador" : "Associar orientador", data => mutate("PATCH", "", data), "Orientador associado."));
  }

  function advisorReview(mutate) {
    return actions(...[["approve", "Aprovar submissão", "success"], ["reject", "Rejeitar submissão", "danger"]]
      .map(([route, text, style]) => button(text, () => confirmed(text + "? A decisão não pode ser desfeita.",
        () => mutate("POST", route + "/"), "Decisão registrada."), style)));
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
    const uploadStatus = el("p", { class: "file-hint", role: "status" });
    const checkUpload = async () => {
      const data = await api("thesis", path + "upload-status/");
      uploadStatus.textContent = "Processamento do PDF: " + (data.upload_status ? label(data.upload_status) :
        (work.file_sha256 ? "PDF registrado" : "nenhum envio recente"));
    };
    const mutate = async (method, suffix = "", body) => {
      await api("thesis", path + suffix, { method, body });
      await load();
      if (method === "DELETE") detail.replaceChildren();
      else await open(id);
    };
    summary.append(actions(button("Consultar processamento do PDF", () => run(checkUpload), "secondary")), uploadStatus);

    if (profile.role === "student" && draft) summary.append(...studentDraftPanels(work, mutate));
    if (profile.role === "coordinator" && draft) summary.append(coordinatorPanel(work, mutate));
    if (profile.role === "advisor" && work.status === "submitted") summary.append(advisorReview(mutate));
    if (["coordinator", "advisor"].includes(profile.role) && work.status === "advisor_approved") {
      summary.append(actions(link("Propor banca", "banca.html" + query({ thesis: work.id }))));
    }
    if (["coordinator", "admin"].includes(profile.role) && ["advisor_approved", "defense_approved"].includes(work.status)) {
      summary.append(actions(link("Preparar publicação", "publicacao.html" + query({ id: work.id }))));
    }
    detail.replaceChildren(summary);
    reveal(detail);
  }

  content.replaceChildren(...[create, search, list, detail].filter(Boolean));
  await load();
  const selected = new URLSearchParams(location.search).get("id");
  if (selected) await open(selected);
});
