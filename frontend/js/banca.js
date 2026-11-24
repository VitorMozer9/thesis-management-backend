"use strict";

start(async profile => {
  const list = el("div");
  const detail = el("div");
  const thesis = new URLSearchParams(location.search).get("thesis") || "";
  let page = 1;
  const capable = ["advisor", "coordinator"].includes(profile.role);

  async function load(current = page) {
    const data = await api("defense", defensePath + query({ page: current }));
    page = current;
    list.replaceChildren(section("Bancas", results(data.results, defense => el("article", { class: "app-row" },
      el("strong", {}, label(defense.status)), el("span", {}, date(defense.starts_at)),
      el("span", {}, defense.thesis_id), button("Detalhes", () => run(() => open(defense.id))))),
    pagination(page, data.has_next, load)));
  }

  async function open(id) {
    const path = recordPath(defensePath, id);
    const defense = await api("defense", path);
    let work;
    try {
      work = await api("thesis", recordPath(thesisPath, defense.thesis_id));
    } catch (error) {
      if (![403, 404].includes(error.status)) throw error;
    }
    const manager = profile.role === "coordinator" || (profile.role === "advisor" && work?.advisor_id === profile.academic_id);
    const editable = ["proposed", "awaiting_confirmations"].includes(defense.status);
    const changes = async (suffix, body, method = "POST") => {
      const response = await api("defense", path + suffix, { method, body });
      await load();
      await open(id);
      return response;
    };
    const summary = section(work?.title || "Detalhes da banca", facts({
      "Situação": label(defense.status), "Banca": id, "Monografia": defense.thesis_id,
      "Início": date(defense.starts_at), "Término": date(defense.ends_at),
      "Local ou reunião": defense.venue || defense.meeting_url
    }));

    if (manager && !["cancelled", "held"].includes(defense.status)) {
      summary.append(actions(button("Cancelar banca", () => {
        if (confirm("Cancelar esta banca?")) run(() => changes("cancel/"), "Banca cancelada.");
      }, "danger")));
    }
    if (manager && defense.status === "scheduled") {
      summary.append(actions(button("Registrar realização", () => run(() => changes("hold/"), "Realização registrada."),
        "success", Date.parse(defense.ends_at) > Date.now())));
    }
    if (manager && editable) {
      summary.append(form([
        field("Início", "starts_at", { type: "datetime-local", required: true }),
        field("Término", "ends_at", { type: "datetime-local", required: true }),
        field("Local presencial", "venue", { maxlength: 255 }), field("Ou link HTTPS", "meeting_url", { type: "url" })
      ], "Agendar", data => {
        if (Boolean(data.venue.trim()) === Boolean(data.meeting_url.trim())) throw new Error("Informe um local ou um link HTTPS.");
        return changes("schedule/", { ...data, starts_at: new Date(data.starts_at).toISOString(),
          ends_at: new Date(data.ends_at).toISOString() });
      }, "Banca agendada."));
    }

    const panels = [summary];
    let own;
    if (profile.role !== "student") {
      const members = await api("defense", path + "members/");
      own = members.find(member => member.academic_id === profile.academic_id);
      const roster = section("Membros e confirmações", results(members, member => {
        const memberPath = recordPath("members/", member.id);
        return el("article", { class: "app-row" },
          el("strong", {}, member.name || member.academic_id), el("span", {}, label(member.invite_status)),
          editable && member.id === own?.id && member.invite_status === "pending" ?
            actions(button("Confirmar", () => run(() => changes(memberPath + "response/", { accept: true }), "Presença confirmada.")),
              button("Recusar", () => run(() => changes(memberPath + "response/", { accept: false }), "Convite recusado."), "danger")) : null,
          manager && editable ? button("Remover", () => {
            if (confirm("Remover o membro da banca?")) run(() => changes(memberPath, undefined, "DELETE"), "Membro removido.");
          }, "danger") : null);
      }));
      if (manager && editable) {
        roster.append(form([field("UUID acadêmico", "academic_id", { required: true })],
          "Convidar membro interno", data => changes("members/", { kind: "internal", ...data }), "Convite registrado."),
        form([field("Nome", "name", { required: true, maxlength: 200 }),
          field("E-mail", "email", { type: "email", required: true, maxlength: 254 })], "Convidar membro externo", async data => {
          const member = await changes("members/", { kind: "external", ...data });
          if (member.token) {
            detail.append(section("Credencial do convite externo", el("p", {}, "Copie o código agora e envie por um canal privado."),
              facts({ "Código": member.token, "Expira em": date(member.expires_at) }),
              link("Página do convite", "convite.html" + query({ defense: id, member: member.id }))));
            detail.lastElementChild.scrollIntoView({ block: "start" });
          }
        }, "Convite registrado."));
      }
      panels.push(roster);
    }

    if (defense.status === "held") {
      let result;
      try {
        result = await api("defense", path + "result/");
      } catch (error) {
        if (error.status !== 409) throw error;
      }
      if (manager || own?.invite_status === "confirmed") {
        const evaluations = await api("defense", path + "evaluations/");
        const panel = section("Avaliações", results(evaluations, item => facts({
          "Avaliador": item.member_id, "Nota": String(item.grade), "Parecer": item.opinion,
          "Recomendação": label(item.recommendation)
        })));
        if (!result && own?.invite_status === "confirmed" && !evaluations.some(item => item.member_id === own.id)) {
          panel.append(form([
            field("Nota", "grade", { type: "number", required: true, min: 0, max: 10, step: "0.01" }),
            field("Parecer", "opinion", { type: "textarea", required: true, maxlength: 5000 }),
            field("Recomendação", "recommendation", { options: [["approved", "Aprovar"], ["conditional", "Aprovar com ressalvas"], ["rejected", "Reprovar"]] })
          ], "Registrar avaliação", data => changes("evaluations/", data), "Avaliação registrada."));
        }
        panels.push(panel);
      }
      panels.push(section("Resultado", result ? facts({ "Resultado": label(result.result), "Média": String(result.average) }) :
        el("p", {}, "Aguardando conclusão das avaliações.")));
    }
    detail.replaceChildren(...panels);
    detail.scrollIntoView({ block: "start" });
  }

  const proposal = capable ? section("Nova proposta", form([
    field("UUID da monografia aprovada pelo orientador", "thesis_id", { required: true, value: thesis })
  ], "Criar proposta", async data => {
    const created = await api("defense", defensePath, { method: "POST", body: data });
    await load(1);
    await open(created.id);
  }, "Proposta criada.", true)) : null;
  content.replaceChildren(...[proposal, list, detail].filter(Boolean));
  await load();
  const selected = new URLSearchParams(location.search).get("id");
  if (selected) await open(selected);
}, { roles: ["advisor", "coordinator", "student"] });
