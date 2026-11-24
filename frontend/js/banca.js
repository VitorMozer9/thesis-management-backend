"use strict";

const recommendations = [["approved", "Aprovar"], ["conditional", "Aprovar com ressalvas"], ["rejected", "Reprovar"]];

function scheduleBody(data) {
  const venue = data.venue.trim();
  const meetingUrl = data.meeting_url.trim();
  if (Boolean(venue) === Boolean(meetingUrl)) throw new Error("Informe somente o local presencial ou somente o link da reunião.");
  if (meetingUrl && !meetingUrl.startsWith("https://")) throw new Error("O link da reunião deve começar com https://.");
  const startsAt = new Date(data.starts_at);
  const endsAt = new Date(data.ends_at);
  if (!(startsAt < endsAt)) throw new Error("O término deve ser posterior ao início.");
  return { starts_at: startsAt.toISOString(), ends_at: endsAt.toISOString(), ...(venue ? { venue } : { meeting_url: meetingUrl }) };
}

function memberName(member) {
  return member?.name || member?.academic_id || "Membro removido";
}

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
      el("strong", {}, defense.starts_at ? date(defense.starts_at) : "Data a definir"),
      el("span", { class: "mode-pill" }, label(defense.status)),
      el("span", { class: "row-meta" }, "Monografia " + defense.thesis_id),
      button("Detalhes", () => run(() => open(defense.id)), "secondary"))), pagination(page, data.has_next, load)));
  }

  async function fetchThesis(id) {
    try {
      return await api("thesis", recordPath(thesisPath, id));
    } catch (error) {
      if (![403, 404].includes(error.status)) throw error;
      return null;
    }
  }

  async function fetchResult(path) {
    try {
      return await api("defense", path + "result/");
    } catch (error) {
      if (error.status !== 409) throw error;
      return null;
    }
  }

  function managementActions(defense, changes) {
    const items = [];
    if (defense.status === "scheduled") {
      const early = Date.parse(defense.ends_at) > Date.now();
      items.push(button("Registrar realização", () => run(() => changes("hold/"), "Realização registrada."), "success", early));
      if (early) items.push(el("span", { class: "row-meta" }, "Disponível após o término agendado."));
    }
    if (!["cancelled", "held"].includes(defense.status)) {
      items.push(button("Cancelar banca", () => confirmed("Cancelar esta banca? A operação não pode ser desfeita.",
        () => changes("cancel/"), "Banca cancelada."), "danger"));
    }
    return items.length ? actions(...items) : null;
  }

  function scheduleForm(changes) {
    return el("div", { class: "subsection" }, el("h3", {}, "Agendar defesa"),
      hint("Todos os convidados precisam confirmar presença e a banca precisa de ao menos um membro interno. Duração entre 15 minutos e 8 horas."),
      form([
        field("Início", "starts_at", { type: "datetime-local", required: true }),
        field("Término", "ends_at", { type: "datetime-local", required: true }),
        field("Local presencial", "venue", { maxlength: 255, help: "Preencha o local ou o link, não ambos." }),
        field("Link da reunião", "meeting_url", { type: "url", maxlength: 500, placeholder: "https://" })
      ], "Agendar", data => changes("schedule/", scheduleBody(data)), "Banca agendada."));
  }

  function rosterPanel(members, own, manager, editable, changes, id) {
    const roster = section("Membros e confirmações", results(members, member => {
      const memberPath = recordPath("members/", member.id);
      return el("article", { class: "app-row" },
        el("strong", {}, memberName(member)), el("span", { class: "row-meta" }, label(member.kind)),
        el("span", { class: "mode-pill" }, label(member.invite_status)),
        editable && member.id === own?.id && member.invite_status === "pending" ?
          actions(button("Confirmar presença", () => run(() => changes(memberPath + "response/", { accept: true }), "Presença confirmada."), "success"),
            button("Recusar", () => confirmed("Recusar o convite para esta banca?", () => changes(memberPath + "response/", { accept: false }), "Convite recusado."), "danger")) : null,
        manager && editable ? button("Remover", () => confirmed("Remover " + memberName(member) + " da banca?",
          () => changes(memberPath, undefined, "DELETE"), "Membro removido."), "danger") : null);
    }, "Nenhum membro convidado."));
    if (!manager || !editable) return roster;

    roster.append(
      el("div", { class: "subsection" }, el("h3", {}, "Convidar membro interno"),
        form([field("UUID acadêmico do docente", "academic_id", { required: true, help: "Identificador acadêmico de orientador ou coordenação do curso." })],
          "Convidar", data => changes("members/", { kind: "internal", academic_id: data.academic_id.trim() }), "Convite registrado.")),
      el("div", { class: "subsection" }, el("h3", {}, "Convidar membro externo"),
        form([field("Nome", "name", { required: true, maxlength: 200 }),
          field("E-mail", "email", { type: "email", required: true, maxlength: 254 })], "Convidar", async data => {
          const member = await changes("members/", { kind: "external", name: data.name.trim(), email: data.email.trim() });
          if (member.token) showExternalCredential(id, member);
        }, "Convite registrado.")));
    return roster;
  }

  function showExternalCredential(id, member) {
    const panel = section("Credencial do convite externo",
      el("p", {}, "Copie o código agora e envie por um canal privado. Ele não será exibido novamente."),
      facts({ "Código": member.token, "Expira em": date(member.expires_at) }),
      actions(link("Página do convite", "convite.html" + query({ defense: id, member: member.id }))));
    detail.append(panel);
    reveal(panel);
  }

  async function evaluationPanels(path, members, own, manager, changes) {
    const panels = [];
    const result = await fetchResult(path);
    if (manager || own?.invite_status === "confirmed") {
      const evaluations = await api("defense", path + "evaluations/");
      const panel = section("Avaliações", results(evaluations, item => el("div", { class: "evaluation" }, facts({
        "Avaliador": memberName(members.find(member => member.id === item.member_id)), "Nota": String(item.grade),
        "Recomendação": label(item.recommendation), "Parecer": item.opinion, "Registrada em": date(item.created_at)
      })), "Nenhuma avaliação registrada."));
      const canEvaluate = own?.kind === "internal" && own.invite_status === "confirmed";
      if (!result && canEvaluate && !evaluations.some(item => item.member_id === own.id)) {
        panel.append(el("div", { class: "subsection" }, el("h3", {}, "Registrar minha avaliação"), form([
          field("Nota (0 a 10)", "grade", { type: "number", required: true, min: 0, max: 10, step: "0.01" }),
          field("Recomendação", "recommendation", { options: recommendations }),
          field("Parecer", "opinion", { type: "textarea", required: true, maxlength: 5000 })
        ], "Registrar avaliação", data => changes("evaluations/", data), "Avaliação registrada.",
        { confirmation: "Registrar a avaliação? Ela não poderá ser alterada." })));
      }
      panels.push(panel);
    }
    panels.push(section("Resultado", result ? facts({ "Resultado": label(result.result), "Média": String(result.average) }) :
      el("p", {}, "Aguardando a conclusão de todas as avaliações.")));
    return panels;
  }

  async function open(id) {
    const path = recordPath(defensePath, id);
    const defense = await api("defense", path);
    const work = await fetchThesis(defense.thesis_id);
    const manager = profile.role === "coordinator" || (profile.role === "advisor" && work?.advisor_id === profile.academic_id);
    const editable = ["proposed", "awaiting_confirmations"].includes(defense.status);
    const changes = async (suffix, body, method = "POST") => {
      const response = await api("defense", path + suffix, { method, body });
      await load();
      await open(id);
      return response;
    };

    const summary = section(work?.title || "Detalhes da banca", facts({
      "Situação": label(defense.status), "Monografia": work ? label(work.status) + " · " + defense.thesis_id : defense.thesis_id,
      "Início": date(defense.starts_at), "Término": date(defense.ends_at),
      "Local ou reunião": defense.venue || defense.meeting_url, "Identificador da banca": id
    }));
    const management = manager ? managementActions(defense, changes) : null;
    if (management) summary.append(management);
    if (manager && editable) summary.append(scheduleForm(changes));

    const panels = [summary];
    let members = [];
    let own;
    if (profile.role !== "student") {
      members = await api("defense", path + "members/");
      own = members.find(member => member.academic_id === profile.academic_id);
      panels.push(rosterPanel(members, own, manager, editable, changes, id));
    }
    if (defense.status === "held") panels.push(...await evaluationPanels(path, members, own, manager, changes));

    detail.replaceChildren(...panels);
    reveal(detail);
  }

  const proposal = capable ? section("Nova proposta",
    hint("A monografia precisa estar aprovada pelo orientador. Use o botão “Propor banca” na página de Monografias para preencher automaticamente."),
    form([field("UUID da monografia", "thesis_id", { required: true, value: thesis })], "Criar proposta", async data => {
      const created = await api("defense", defensePath, { method: "POST", body: { thesis_id: data.thesis_id.trim() } });
      await load(1);
      await open(created.id);
    }, "Proposta criada.", { reset: true })) : null;
  content.replaceChildren(...[proposal, list, detail].filter(Boolean));
  await load();
  const selected = new URLSearchParams(location.search).get("id");
  if (selected) await open(selected);
}, { roles: ["advisor", "coordinator", "student"] });
