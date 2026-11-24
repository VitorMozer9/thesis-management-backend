from datetime import timedelta

from notifications.domain import Failure, MESSAGES


class ProcessNotifications:
    def __init__(self, records, contacts, mail, clock, max_attempts):
        self.records = records
        self.contacts = contacts
        self.mail = mail
        self.clock = clock
        self.max_attempts = max_attempts

    def expand(self, event):
        academic, external = self.contacts.recipients(event)
        if not academic and not external:
            raise Failure("no_recipients")
        subject = MESSAGES[event.kind][0]
        self.records.enqueue(event, academic, external, subject)

    def deliver(self, notification):
        address = notification.recipient
        if notification.academic_id:
            notification.account_id, address = self.contacts.account(notification.academic_id)
        self.mail.send(notification, address)
        notification.sent_at = self.clock()

    def run_next(self, queue):
        process = self.expand if queue == "events" else self.deliver
        with self.records.claim(queue, self.clock()) as job:
            if job is None:
                return False
            job.attempts += 1
            try:
                process(job)
            except Failure as exc:
                job.error_code = exc.code
                if exc.permanent or job.attempts >= self.max_attempts:
                    job.status = "failed"
                else:
                    job.next_attempt = self.clock() + timedelta(seconds=min(3600, 5 * 2 ** min(job.attempts - 1, 10)))
            else:
                job.status = "sent"
                job.error_code = ""
            self.records.save(job)
            return True
