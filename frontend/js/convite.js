"use strict";

const invitePattern = "[A-Za-z0-9_\\-]{43}";

start(() => {
  const params = new URLSearchParams(location.search);
  content.replaceChildren(section("Convite externo",
    el("p", {}, "Informe o código recebido da coordenação ou da orientação. O código é válido por 48 horas e pode ser usado uma única vez."),
    form([
      field("UUID da banca", "defense", { value: params.get("defense") || "", required: true }),
      field("UUID do convite", "member", { value: params.get("member") || "", required: true }),
      field("Código do convite", "token", { type: "password", required: true, autocomplete: "off", pattern: invitePattern,
        title: "Código de 43 caracteres." }),
      field("Resposta", "accept", { options: [["yes", "Confirmar presença"], ["no", "Recusar"]] })
    ], "Enviar resposta", async data => {
      const path = recordPath(defensePath, data.defense.trim()) + recordPath("members/", data.member.trim()) + "external-response/";
      const response = await api("defense", path, { method: "POST", auth: false, body: { token: data.token.trim(), accept: data.accept === "yes" } });
      content.replaceChildren(section("Resposta registrada", el("p", {}, "Situação do convite: " + label(response.invite_status))));
    })));
}, { publicPage: true });
