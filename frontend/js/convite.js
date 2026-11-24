"use strict";

start(() => {
  const params = new URLSearchParams(location.search);
  content.replaceChildren(section("Convite externo", form([
    field("UUID da banca", "defense", { value: params.get("defense") || "", required: true }),
    field("UUID do convite", "member", { value: params.get("member") || "", required: true }),
    field("Código do convite", "token", { type: "password", required: true, autocomplete: "off" }),
    field("Resposta", "accept", { options: [["yes", "Confirmar presença"], ["no", "Recusar"]] })
  ], "Enviar resposta", async data => {
    const path = recordPath(defensePath, data.defense) + recordPath("members/", data.member) + "external-response/";
    const response = await api("defense", path, { method: "POST", auth: false, body: { token: data.token, accept: data.accept === "yes" } });
    content.replaceChildren(section("Resposta registrada", el("p", {}, label(response.invite_status))));
  })));
}, { publicPage: true });
