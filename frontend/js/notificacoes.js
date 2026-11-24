"use strict";

start(async () => {
  const { results: entries } = await api("notification", notificationPath);
  const detail = el("div");
  content.replaceChildren(section("Notificações recentes", results(entries, entry => el("article", { class: "app-row" },
    el("strong", {}, entry.subject), el("span", {}, label(entry.status)), el("span", {}, date(entry.created_at)),
    button("Detalhes", () => run(async () => {
      const row = await api("notification", recordPath(notificationPath, entry.id));
      detail.replaceChildren(section(row.subject, facts({
        "Situação": label(row.status), "Criada em": date(row.created_at), "Enviada em": date(row.sent_at)
      })));
      detail.scrollIntoView({ block: "start" });
    }))))), detail);
});
