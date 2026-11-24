"use strict";

start(async () => {
  const listArea = el("div");

  function render(entries) {
    listArea.replaceChildren(section("Notificações recentes",
      results(entries, entry => el("article", { class: "app-row notification-row" },
        el("strong", {}, entry.subject),
        el("span", { class: "row-meta" }, label(entry.event__kind)),
        el("span", { class: "mode-pill" }, label(entry.status)),
        el("span", { class: "row-meta" }, "Criada em " + date(entry.created_at) + (entry.sent_at ? " · enviada em " + date(entry.sent_at) : ""))),
      "Você ainda não recebeu notificações."),
      actions(button("Atualizar", () => run(load), "secondary"))));
  }

  async function load() {
    const { results: entries } = await api("notification", notificationPath);
    render(entries);
  }

  content.replaceChildren(listArea);
  await load();
});
