"use strict";

start(() => {
  const selected = new URLSearchParams(location.search).get("id") || "";
  const thesisId = () => field("UUID da monografia", "id", { value: selected, required: true });
  const path = id => catalogPath + "admin/" + segment(id) + "/";
  const state = el("p", { class: "notice notice-info", role: "status", hidden: true });
  const show = data => {
    state.hidden = false;
    state.textContent = data.state === "published" ? "Monografia publicada." : "Dados recebidos. Aguardando requisitos de publicação.";
  };

  content.replaceChildren(state,
    section("Metadados públicos", form([thesisId(),
      field("Título", "title", { required: true, maxlength: 255 }), field("Autor", "author", { required: true, maxlength: 200 }),
      field("Orientador", "advisor", { required: true, maxlength: 200 }),
      field("Palavras-chave separadas por vírgulas", "keywords", { required: true }),
      field("Ano da defesa, se conferido", "reported_year", { type: "number", min: 1900, max: 9999 })
    ], "Salvar metadados", async ({ id, reported_year, keywords, ...body }) => {
      body.keywords = words(keywords);
      if (reported_year) body.reported_year = Number(reported_year);
      show(await api("repository", path(id) + "metadata/", { method: "PUT", body }));
    })),
    section("Documentos para publicação", form([thesisId(),
      field("Tipo de documento", "kind", { options: [
        ["authorization", "Termo de autorização assinado"], ["final", "PDF final"], ["corrected", "PDF corrigido"]
      ] }), field("PDF de até 20 MiB", "file", { type: "file", accept: "application/pdf,.pdf", required: true })
    ], "Enviar documento", async data => {
      const file = pdf(data.file);
      if (!crypto.subtle) throw new Error("Abra pelo endereço local ou por HTTPS para calcular o SHA-256.");
      const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
      const hash = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
      const body = new FormData();
      body.append("file", file);
      body.append("kind", data.kind);
      body.append("sha256", hash);
      show(await api("repository", path(data.id) + "documents/", { method: "POST", body }));
    })));
}, { roles: ["admin", "coordinator"] });
