from repository.domain import Conflict, Forbidden


class PublicationService:
    def __init__(self, records, documents, theses, defenses):
        self.records = records
        self.documents = documents
        self.theses = theses
        self.defenses = defenses

    def administer(self, thesis_id, actor, token, *, metadata=None, document=None):
        if actor.role not in ("coordinator", "admin"):
            raise Forbidden
        original = self.theses.verify(thesis_id, actor, token)

        with self.records.transaction():
            entry = self.records.lock(thesis_id, actor.course_id)
            if entry.course_id != actor.course_id:
                raise Forbidden
            if entry.published_at:
                raise Conflict("A publicação está fechada.")
            if metadata is not None:
                if set(metadata) - {"title", "author", "advisor", "keywords", "reported_year"}:
                    raise Conflict("Metadados inválidos.")
                action = "metadata_updated" if entry.title else "metadata_registered"
                for name, value in metadata.items():
                    setattr(entry, name, value)
            else:
                kind, digest = document["kind"], document["sha256"]
                if kind not in ("authorization", "final", "corrected"):
                    raise Conflict("Tipo de documento inválido.")
                previous = entry.term_hash if kind == "authorization" else entry.final_hash
                if kind == "authorization":
                    if digest == entry.final_hash:
                        raise Conflict("O termo precisa ser um documento separado.")
                    entry.term_hash = digest
                else:
                    if digest == entry.term_hash:
                        raise Conflict("A versão final precisa ser um documento separado.")
                    if kind == "corrected" and original is None:
                        raise Conflict("A correção exige a versão acadêmica aprovada pelo orientador.")
                    if kind == "corrected" and (digest == original or digest == entry.final_hash and not entry.corrected):
                        raise Conflict("Envie a versão corrigida.")
                    entry.final_hash = digest
                    entry.corrected = kind == "corrected"
                self.documents.receive(thesis_id, document["file"], digest)
                action = f"{kind}_replaced" if previous and previous != digest else f"{kind}_registered"
            self.records.audit(entry, action, actor.account_id)
            return self.save(entry, actor.account_id)

    def complete(self, event):
        if self.records.seen(event):
            return
        year = self.defenses.verify(event)
        with self.records.transaction():
            entry = self.records.lock(event.thesis_id, event.course_id)
            if not self.records.receive(event):
                return
            if entry.course_id != event.course_id or entry.defense_id and (
                entry.defense_id != event.defense_id or entry.result != event.result
                or entry.defense_year and year != entry.defense_year
            ):
                raise Conflict("Resultado incompatível com o registro existente.")
            entry.defense_id = event.defense_id
            entry.result = event.result
            entry.defense_year = year
            self.save(entry, event_id=event.event_id)

    def save(self, entry, actor_id=None, event_id=None):
        if not entry.published_at and entry.ready():
            for digest in (entry.final_hash, entry.term_hash):
                with self.documents.verified(entry.thesis_id, digest):
                    pass
            self.records.publish(entry)
            self.records.audit(entry, "published", actor_id, event_id)
        self.records.save(entry)
        return "published" if entry.published_at else "pending"
