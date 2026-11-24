"use strict";

async function sha256Hex(file) {
  if (!crypto.subtle) throw new Error("Abra pelo endereço local ou por HTTPS para calcular o SHA-256.");
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
}

start(() => {
  const selected = new URLSearchParams(location.search).get("id") || "";
  const thesisId = () => field("UUID da monografia", "id", { value: selected, required: true });
  const path = id => catalogPath + "admin/" + segment(id.trim()) + "/";
  const state = el("p", { class: "notice notice-info", role: "status", hidden: true });
  const show = data => {
    state.hidden = false;
    state.className = "notice " + (data.state === "published" ? "notice-success" : "notice-info");
    state.textContent = data.state === "published" ? "Monografia publicada no repositório." :
      "Dados recebidos. A publicação ocorrerá quando todos os requisitos forem atendidos.";
  };

  content.replaceChildren(state,
    section("Requisitos de publicação", el("ul", { class: "checklist" },
      el("li", {}, "Banca concluída com resultado aprovado; se aprovada com ressalvas, é necessário o PDF corrigido."),
      el("li", {}, "Metadados públicos: título, autor, orientador e palavras-chave."),
      el("li", {}, "Termo de autorização assinado e PDF final, em arquivos distintos."))),
    section("Metadados públicos", form([thesisId(),
      field("Título", "title", { required: true, maxlength: 255 }), field("Autor", "author", { required: true, maxlength: 200 }),
      field("Orientador", "advisor", { required: true, maxlength: 200 }),
      field("Palavras-chave separadas por vírgulas", "keywords", { required: true, help: "Até 30 palavras-chave com até 100 caracteres cada." }),
      field("Ano da defesa, se conferido", "reported_year", { type: "number", min: 1900, max: 9999,
        help: "Se informado, precisa coincidir com o ano registrado pela banca." })
    ], "Salvar metadados", async ({ id, reported_year, keywords, ...fields }) => {
      const body = { title: fields.title.trim(), author: fields.author.trim(), advisor: fields.advisor.trim(), keywords: words(keywords) };
      if (!body.keywords.length) throw new Error("Informe ao menos uma palavra-chave.");
      if (reported_year) body.reported_year = Number(reported_year);
      show(await api("repository", path(id) + "metadata/", { method: "PUT", body }));
    })),
    section("Documentos para publicação", form([thesisId(),
      field("Tipo de documento", "kind", { options: [
        ["authorization", "Termo de autorização assinado"], ["final", "PDF final"], ["corrected", "PDF corrigido"]
      ] }), field("PDF de até 20 MiB", "file", { type: "file", accept: "application/pdf,.pdf", required: true })
    ], "Enviar documento", async data => {
      const file = pdf(data.file);
      const body = new FormData();
      body.append("file", file);
      body.append("kind", data.kind);
      body.append("sha256", await sha256Hex(file));
      show(await api("repository", path(data.id) + "documents/", { method: "POST", body }));
      content.querySelector('input[type="file"]').value = "";
    })));
}, { roles: ["admin", "coordinator"] });
