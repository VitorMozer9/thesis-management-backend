from contextlib import nullcontext
from unittest.mock import patch
from uuid import uuid4

from allauth.account.models import EmailAddress
from django.test import SimpleTestCase

from config import dependencies
from identity.adapters.outbound.persistence.audit_models import AccountAuditModel
from identity.adapters.outbound.persistence.django_account_audit import DjangoAccountAudit
from identity.adapters.outbound.persistence.models import User
from identity.application.exceptions import AdministrationConflictError
from identity.application.ports import AccountAuditAction, AdministrationLock
from identity.application.use_case.set_account_active import SetAccountActiveUseCase
from identity.domain.account import Account, Role
from identity.tests.support import TEST_PASSWORD, IdentityTestCase


NEW_PASSWORD = "Initial-Secret-Phrase-91"


class AdministrationTestCase(IdentityTestCase):

    def setUp(self):
        super().setUp()

        self.admin = self.provision(role=Role.ADMIN, name="Admin Principal")
        self.admin_token = self.issue_token(self.admin)

    def api(self, method, path, token=None, body=None):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        request = getattr(self.client, method)

        if method == "get":
            return request(path, **headers)

        if body is None:
            return request(path, content_type="application/json", **headers)

        return request(path, body, content_type="application/json", **headers)

    def create_body(self, **changes):
        return {
            "name": "Nova Estudante",
            "email": f"{uuid4().hex[:10]}@example.edu",
            "role": "student",
            "course_id": str(self.course_id),
            "password": NEW_PASSWORD,
            **changes,
        }

    def audits(self, target_id, action=None):
        records = AccountAuditModel.objects.filter(target_account_id=target_id)

        if action:
            records = records.filter(action=action)

        return list(records.order_by("occurred_at"))


class CreateUserTests(AdministrationTestCase):

    def test_admin_creates_account_without_exposing_password(self):
        body = self.create_body(email="Nova.Estudante@Example.EDU")
        response = self.api("post", "/api/users/", self.admin_token, body)

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response["Location"], f"/api/users/{response.json()['id']}/")
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertNotIn("password", response.json())
        self.assertNotIn(NEW_PASSWORD, response.content.decode())

        user = User.objects.get(id=response.json()["id"])

        self.assertEqual(user.email, "nova.estudante@example.edu")
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(user.check_password(NEW_PASSWORD))
        self.assertTrue(EmailAddress.objects.filter(user=user, verified=True, primary=True).exists())

        audit = self.audits(user.id, AccountAuditAction.CREATED)[0]

        self.assertEqual(audit.actor_account_id, self.admin.id)
        self.assertEqual(audit.changes["role"], "student")
        self.assertNotIn("password", audit.changes)
        self.assertNotIn(NEW_PASSWORD, str(audit.changes))

    def test_created_account_can_login_with_initial_password(self):
        response = self.api("post", "/api/users/", self.admin_token, self.create_body())

        self.assertEqual(self.login(response.json()["email"], NEW_PASSWORD).status_code, 200)

    def test_preserves_provided_academic_id(self):
        academic_id = uuid4()
        response = self.api("post", "/api/users/", self.admin_token, self.create_body(academic_id=str(academic_id)))

        self.assertEqual(response.json()["academic_id"], str(academic_id))

        duplicate = self.api("post", "/api/users/", self.admin_token, self.create_body(academic_id=str(academic_id)))

        self.assertEqual(duplicate.status_code, 400)

    def test_requires_authentication(self):
        response = self.api("post", "/api/users/", body=self.create_body())

        self.assertEqual(response.status_code, 401)
        self.assertEqual(User.objects.count(), 1)

    def test_rejects_non_administrators(self):
        for role in (Role.STUDENT, Role.ADVISOR, Role.COORDINATOR):
            with self.subTest(role=role):
                token = self.issue_token(self.provision(role=role))

                self.assertEqual(self.api("post", "/api/users/", token, self.create_body()).status_code, 403)
                self.assertEqual(self.api("get", "/api/users/", token).status_code, 403)

        self.assertEqual(User.objects.filter(name="Nova Estudante").count(), 0)

    def test_rejects_duplicate_email_ignoring_case(self):
        self.api("post", "/api/users/", self.admin_token, self.create_body(email="dup@example.edu"))
        response = self.api("post", "/api/users/", self.admin_token, self.create_body(email="DUP@example.edu"))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.filter(email="dup@example.edu").count(), 1)

    def test_rejects_invalid_fields(self):
        cases = {
            "blank_name": {"name": "   "},
            "long_name": {"name": "x" * 151},
            "missing_course": {"course_id": None},
            "invalid_role": {"role": "root"},
            "invalid_course": {"course_id": "not-a-uuid"},
            "invalid_academic_id": {"academic_id": "123"},
            "invalid_email": {"email": "not-an-email"},
            "weak_password": {"password": "12345678"},
            "unexpected_field": {"is_active": False},
            "account_id": {"id": str(uuid4())},
        }

        for case, changes in cases.items():
            with self.subTest(case=case):
                response = self.api("post", "/api/users/", self.admin_token, self.create_body(**changes))
                self.assertEqual(response.status_code, 400, response.content)
                self.assertNotIn(NEW_PASSWORD, response.content.decode())

        self.assertEqual(User.objects.count(), 1)

    def test_cannot_create_administrator_through_api(self):
        response = self.api("post", "/api/users/", self.admin_token, self.create_body(role="admin"))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(User.objects.filter(role=Role.ADMIN).count(), 1)

    def test_cli_provisioning_is_audited_without_actor(self):
        account = self.provision(role=Role.ADVISOR)
        audit = self.audits(account.id, AccountAuditAction.CREATED)[0]

        self.assertIsNone(audit.actor_account_id)


class ListAndGetUserTests(AdministrationTestCase):

    def setUp(self):
        super().setUp()

        self.other_course = uuid4()
        self.alice = self.provision(name="Alice Martins", email="alice@example.edu")
        self.bruno = self.provision(role=Role.ADVISOR, name="Bruno Lima", email="bruno@uni.example")
        self.carla = self.provision(name="Carla Dias", course_id=self.other_course, is_active=False)

    def list_ids(self, **params):
        response = self.client.get("/api/users/", params, HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        self.assertEqual(response.status_code, 200, response.content)

        return {item["id"] for item in response.json()["results"]}

    def test_filters_by_role_course_state_and_search(self):
        self.assertEqual(self.list_ids(role="advisor"), {str(self.bruno.id)})
        self.assertEqual(self.list_ids(course_id=str(self.other_course)), {str(self.carla.id)})
        self.assertEqual(self.list_ids(is_active="false"), {str(self.carla.id)})
        self.assertNotIn(str(self.carla.id), self.list_ids(is_active="true"))
        self.assertEqual(self.list_ids(search="MARTINS"), {str(self.alice.id)})
        self.assertEqual(self.list_ids(search="uni.example"), {str(self.bruno.id)})
        self.assertEqual(self.list_ids(role="student", is_active="true"), {str(self.alice.id)})

    def test_paginates_in_stable_order(self):
        first = self.client.get("/api/users/", {"page_size": 2}, HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        last = self.client.get("/api/users/", {"page_size": 2, "page": 2}, HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")

        self.assertTrue(first.json()["has_next"])
        self.assertFalse(last.json()["has_next"])

        emails = [item["email"] for item in first.json()["results"] + last.json()["results"]]

        self.assertEqual(emails, sorted(emails))
        self.assertEqual(len(set(emails)), 4)

    def test_rejects_invalid_query_parameters(self):
        for params in ({"page_size": 101}, {"page": 0}, {"role": "root"}, {"unknown": "1"}, {"course_id": "x"}):
            with self.subTest(params=params):
                response = self.client.get("/api/users/", params, HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
                self.assertEqual(response.status_code, 400)

    def test_gets_account_by_uuid(self):
        response = self.api("get", f"/api/users/{self.bruno.id}/", self.admin_token)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["academic_id"], str(self.bruno.academic_id))
        self.assertEqual(set(response.json()), {"id", "name", "email", "role", "academic_id", "course_id", "is_active"})

        self.assertEqual(self.api("get", f"/api/users/{uuid4()}/", self.admin_token).status_code, 404)
        self.assertEqual(self.api("get", "/api/users/not-a-uuid/", self.admin_token).status_code, 404)
        self.assertEqual(self.api("get", f"/api/users/{self.bruno.id}/").status_code, 401)


class UpdateUserTests(AdministrationTestCase):

    def setUp(self):
        super().setUp()

        self.student = self.provision(name="Diego Alves")

    def patch(self, account_id, body, token=None):
        return self.api("patch", f"/api/users/{account_id}/", token or self.admin_token, body)

    def test_updates_allowed_fields_and_audits_only_changes(self):
        new_course = uuid4()
        response = self.patch(self.student.id, {
            "name": "Diego Alves Souza",
            "email": "Diego.Novo@Example.EDU",
            "course_id": str(new_course),
            "role": "advisor",
        })

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["email"], "diego.novo@example.edu")
        self.assertEqual(response.json()["academic_id"], str(self.student.academic_id))
        self.assertEqual(response.json()["id"], str(self.student.id))

        changes = self.audits(self.student.id, AccountAuditAction.UPDATED)[0].changes

        self.assertEqual(set(changes), {"name", "email", "course_id", "role"})
        self.assertEqual(changes["role"], {"from": "student", "to": "advisor"})
        self.assertEqual(EmailAddress.objects.get(user_id=self.student.id).email, "diego.novo@example.edu")
        self.assertEqual(self.login("diego.novo@example.edu").status_code, 200)
        self.assertEqual(self.login(self.student.email).status_code, 401)

    def test_unchanged_values_do_not_create_audit(self):
        response = self.patch(self.student.id, {"name": self.student.name})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.audits(self.student.id, AccountAuditAction.UPDATED), [])

    def test_rejects_immutable_and_undeclared_fields(self):
        for body in (
            {"academic_id": str(uuid4())},
            {"id": str(uuid4())},
            {"is_active": False},
            {"password": "Another-Password-55"},
            {"name": "X", "is_staff": True},
            {},
        ):
            with self.subTest(body=body):
                self.assertEqual(self.patch(self.student.id, body).status_code, 400)

        user = User.objects.get(id=self.student.id)

        self.assertEqual(user.academic_id, self.student.academic_id)
        self.assertEqual(user.name, self.student.name)
        self.assertTrue(user.check_password(TEST_PASSWORD))

    def test_rejects_invalid_academic_link(self):
        for body in ({"course_id": None}, {"name": ""}, {"role": "root"}):
            with self.subTest(body=body):
                self.assertEqual(self.patch(self.student.id, body).status_code, 400)

    def test_rejects_duplicate_email(self):
        other = self.provision()

        self.assertEqual(self.patch(self.student.id, {"email": other.email.upper()}).status_code, 400)

    def test_blocks_privilege_escalation(self):
        self.assertEqual(self.patch(self.student.id, {"role": "admin"}).status_code, 403)
        self.assertEqual(self.patch(self.admin.id, {"role": "coordinator"}).status_code, 403)

        other_admin = self.provision(role=Role.ADMIN)

        self.assertEqual(self.patch(other_admin.id, {"role": "student"}).status_code, 403)

        coordinator = self.provision(role=Role.COORDINATOR)
        coordinator_token = self.issue_token(coordinator)

        self.assertEqual(self.patch(coordinator.id, {"role": "admin"}, coordinator_token).status_code, 403)
        self.assertEqual(self.patch(self.student.id, {"name": "X"}, coordinator_token).status_code, 403)
        self.assertEqual(User.objects.get(id=self.student.id).role, Role.STUDENT)
        self.assertEqual(User.objects.get(id=coordinator.id).role, Role.COORDINATOR)

    def test_admin_may_change_own_profile_fields_but_not_role(self):
        self.assertEqual(self.patch(self.admin.id, {"name": "Admin Renomeado"}).status_code, 200)
        self.assertEqual(self.patch(self.admin.id, {"role": "admin", "name": "Admin"}).status_code, 200)
        self.assertEqual(User.objects.get(id=self.admin.id).role, Role.ADMIN)

    def test_unknown_account_returns_404(self):
        self.assertEqual(self.patch(uuid4(), {"name": "X"}).status_code, 404)


class ActivationTests(AdministrationTestCase):

    def setUp(self):
        super().setUp()

        self.student = self.provision()

    def post(self, account_id, action, token=None, body=None):
        return self.api("post", f"/api/users/{account_id}/{action}/", token or self.admin_token, body)

    def test_deactivation_blocks_login_and_reactivation_restores_it(self):
        response = self.post(self.student.id, "deactivate")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_active"])
        self.assertEqual(self.login(self.student.email).status_code, 401)
        self.assertTrue(User.objects.filter(id=self.student.id).exists())

        self.assertEqual(self.post(self.student.id, "activate").status_code, 200)
        self.assertEqual(self.login(self.student.email).status_code, 200)

        actions = [record.action for record in self.audits(self.student.id)]

        self.assertEqual(actions, ["account.created", "account.deactivated", "account.activated"])

    def test_repeated_requests_are_idempotent(self):
        self.post(self.student.id, "deactivate")
        self.assertEqual(self.post(self.student.id, "deactivate").status_code, 200)

        self.assertEqual(len(self.audits(self.student.id, AccountAuditAction.DEACTIVATED)), 1)

    def test_requires_empty_body(self):
        self.assertEqual(self.post(self.student.id, "deactivate", body={"reason": "x"}).status_code, 400)
        self.assertTrue(User.objects.get(id=self.student.id).is_active)

    def test_deactivated_account_token_loses_profile_access(self):
        token = self.issue_token(self.student)
        self.post(self.student.id, "deactivate")

        self.assertEqual(self.api("get", "/api/auth/me/", token).status_code, 401)

    def test_admin_cannot_deactivate_own_account(self):
        self.assertEqual(self.post(self.admin.id, "deactivate").status_code, 403)
        self.assertTrue(User.objects.get(id=self.admin.id).is_active)

    def test_last_active_administrator_is_preserved(self):
        second = self.provision(role=Role.ADMIN)

        self.assertEqual(self.post(second.id, "deactivate").status_code, 200)
        self.assertEqual(self.post(self.admin.id, "deactivate").status_code, 403)
        self.assertEqual(User.objects.filter(role=Role.ADMIN, is_active=True).count(), 1)

    def test_deactivated_admin_cannot_administer_with_previous_token(self):
        second = self.provision(role=Role.ADMIN)
        second_token = self.issue_token(second)

        self.post(second.id, "deactivate")

        for method, path, body in (
            ("get", "/api/users/", None),
            ("get", f"/api/users/{self.student.id}/", None),
            ("post", "/api/users/", self.create_body()),
            ("patch", f"/api/users/{self.student.id}/", {"name": "X"}),
            ("post", f"/api/users/{self.student.id}/deactivate/", None),
        ):
            with self.subTest(method=method, path=path):
                self.assertEqual(self.api(method, path, second_token, body).status_code, 401)

        self.assertTrue(User.objects.get(id=self.student.id).is_active)

    def test_demoted_role_is_checked_in_database_not_token(self):
        coordinator = self.provision(role=Role.COORDINATOR)
        token = self.issue_token(coordinator)
        User.objects.filter(id=coordinator.id).update(role=Role.ADMIN)

        self.assertEqual(self.api("get", "/api/users/", token).status_code, 200)

        User.objects.filter(id=coordinator.id).update(role=Role.COORDINATOR)

        self.assertEqual(self.api("get", "/api/users/", token).status_code, 403)


class AuditIntegrityTests(AdministrationTestCase):

    def failing_audit(self):
        return patch.object(DjangoAccountAudit, "record", side_effect=RuntimeError("audit unavailable"))

    def test_audit_failure_rolls_back_creation(self):
        with self.failing_audit(), self.assertRaises(RuntimeError):
            self.api("post", "/api/users/", self.admin_token, self.create_body(email="rollback@example.edu"))

        self.assertFalse(User.objects.filter(email="rollback@example.edu").exists())
        self.assertFalse(EmailAddress.objects.filter(email="rollback@example.edu").exists())

    def test_audit_failure_rolls_back_update_and_deactivation(self):
        student = self.provision(name="Original")

        with self.failing_audit():
            with self.assertRaises(RuntimeError):
                self.api("patch", f"/api/users/{student.id}/", self.admin_token, {"name": "Changed"})

            with self.assertRaises(RuntimeError):
                self.api("post", f"/api/users/{student.id}/deactivate/", self.admin_token)

        user = User.objects.get(id=student.id)

        self.assertEqual(user.name, "Original")
        self.assertTrue(user.is_active)

    def test_audit_records_are_append_only(self):
        student = self.provision()
        record = self.audits(student.id)[0]
        record.action = AccountAuditAction.UPDATED

        with self.assertRaises(ValueError):
            record.save()

        with self.assertRaises(ValueError):
            record.delete()

    def test_history_survives_deactivation(self):
        student = self.provision()
        self.api("post", f"/api/users/{student.id}/deactivate/", self.admin_token)

        self.assertEqual(len(self.audits(student.id)), 2)

    def test_no_http_route_exposes_audit(self):
        for path in ("/api/audit/", "/api/users/audit/", "/admin/"):
            with self.subTest(path=path):
                self.assertEqual(self.api("get", path, self.admin_token).status_code, 404)


class TokenEffectTests(AdministrationTestCase):

    def test_new_tokens_reflect_role_and_course_changes(self):
        advisor = self.provision(role=Role.ADVISOR)
        coordinator = self.provision(role=Role.COORDINATOR)
        old_token = self.issue_token(advisor)

        self.assertIn(str(advisor.academic_id), self.decode(self.issue_token(coordinator))["assignable_advisor_ids"])

        new_course = uuid4()
        self.api("patch", f"/api/users/{advisor.id}/", self.admin_token, {"role": "student", "course_id": str(new_course)})

        claims = self.decode(self.issue_token(advisor))

        self.assertEqual(claims["role"], "student")
        self.assertEqual(claims["course_id"], str(new_course))
        self.assertEqual(claims["sub"], str(advisor.id))
        self.assertEqual(claims["academic_id"], str(advisor.academic_id))
        self.assertNotIn(str(advisor.academic_id), self.decode(self.issue_token(coordinator))["assignable_advisor_ids"])

        self.assertEqual(self.decode(old_token)["role"], "advisor")

    def test_issued_token_keeps_contract_claims(self):
        claims = self.decode(self.admin_token)

        self.assertEqual(
            set(claims),
            {"iss", "aud", "sub", "academic_id", "role", "course_id", "iat", "exp", "jti"},
        )


class LastAdministratorGuardTests(SimpleTestCase):

    def test_refuses_to_leave_no_active_administrator(self):
        actor = Account.provision(name="A", email="a@example.edu", role=Role.ADMIN, course_id=uuid4())
        target = Account.provision(name="B", email="b@example.edu", role=Role.ADMIN, course_id=uuid4())

        class LockedAccounts:
            def lock_for_administration(self, actor_id, target_id=None):
                return AdministrationLock(actor=actor, target=target, active_admin_ids=frozenset({target.id}))

        class NoTransaction:
            def transaction(self):
                return nullcontext()

        use_case = SetAccountActiveUseCase(accounts=LockedAccounts(), unit_of_work=NoTransaction(), audit=None)

        with self.assertRaises(AdministrationConflictError):
            use_case.execute(actor.id, target.id, active=False)
