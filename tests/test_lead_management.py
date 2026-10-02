"""Integration checks for lead permissions, edits, completion, and restart.

All records live in a temporary SQLite database that is removed afterward.
No Supabase or production database is contacted by this suite.
"""

from __future__ import annotations

import os
import tempfile
import unittest
import uuid
from pathlib import Path

os.environ["NEXSTEP_FAST_HASH"] = "1"

from database.connection import get_connection
from services.action_service import complete_action
from services.admin_service import set_company_administrator
from services.auth_service import set_user_password
from services.comment_service import list_comments_for_lead
from services.lead_edit_service import update_lead_details
from services.lead_permissions import editable_lead
from services.new_lead_service import create_lead_with_first_action
from services.reactivation_service import reactivate_lead
from services.seed_service import ensure_seed_data
from utils.i18n import t


class LeadManagementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(dir=Path(__file__).parents[1] / "tmp")
        cls.conn = get_connection(Path(cls.temporary.name) / "leads.db")
        ensure_seed_data(cls.conn)
        cls.org_id = cls.conn.execute("SELECT id FROM organizations WHERE slug = 'les-confiotes'").fetchone()["id"]
        cls.global_user_id = cls.conn.execute("SELECT id FROM users WHERE is_global_admin = 1").fetchone()["id"]
        cls.agents = cls.conn.execute("""SELECT ou.id, ou.user_id FROM organization_users ou
            WHERE ou.organization_id = ? ORDER BY ou.id LIMIT 2""", (cls.org_id,)).fetchall()
        for agent in cls.agents:
            set_user_password(cls.conn, agent["user_id"], "TestPassword123")

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        cls.temporary.cleanup()

    def new_lead(self, owner=None):
        owner = owner or self.agents[0]["id"]
        return create_lead_with_first_action(self.conn, organization_id=self.org_id,
            actor_org_user_id=owner, lead_name=f"Test {uuid.uuid4().hex}",
            contacts=[{"full_name": "Initial Person", "role_title": "Buyer", "phone_raw": "123"}])

    def contact_payload(self, lead_id, **changes):
        row = self.conn.execute("SELECT * FROM contacts WHERE lead_id = ? ORDER BY created_at LIMIT 1", (lead_id,)).fetchone()
        payload = {key: row[key] or "" for key in
                   ("id", "full_name", "role_title", "phone_raw", "email", "whatsapp", "channel_notes")}
        payload.update(changes)
        return [payload]

    def test_global_admin_can_assign_company_admin(self):
        target = self.agents[1]["id"]
        set_company_administrator(self.conn, actor_user_id=self.global_user_id,
                                  org_user_id=target, enabled=True)
        self.assertEqual(self.conn.execute("SELECT role FROM organization_users WHERE id = ?", (target,)).fetchone()["role"], "company_admin")
        set_company_administrator(self.conn, actor_user_id=self.global_user_id,
                                  org_user_id=target, enabled=False)

    def test_non_global_admin_cannot_assign(self):
        with self.assertRaises(PermissionError):
            set_company_administrator(self.conn, actor_user_id=self.agents[0]["user_id"],
                                      org_user_id=self.agents[1]["id"], enabled=True)

    def test_owner_can_edit_lead_and_contact(self):
        lead_id = self.new_lead()["lead_id"]
        update_lead_details(self.conn, lead_id=lead_id, actor_org_user_id=self.agents[0]["id"],
            password="TestPassword123", name="Renamed lead", city="Douala", context_full="Useful context",
            contacts=self.contact_payload(lead_id, full_name="New Name", role_title="Director", email="Person@Example.com"))
        lead = self.conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        contact = self.conn.execute("SELECT * FROM contacts WHERE lead_id = ?", (lead_id,)).fetchone()
        self.assertEqual((lead["name"], lead["city"], contact["role_title"], contact["email"]),
                         ("Renamed lead", "Douala", "Director", "person@example.com"))

    def test_wrong_password_preserves_details(self):
        lead_id = self.new_lead()["lead_id"]
        with self.assertRaisesRegex(ValueError, "invalid_password"):
            update_lead_details(self.conn, lead_id=lead_id, actor_org_user_id=self.agents[0]["id"],
                password="wrong", name="Changed", city="", context_full="",
                contacts=self.contact_payload(lead_id))
        self.assertNotEqual(self.conn.execute("SELECT name FROM leads WHERE id = ?", (lead_id,)).fetchone()["name"], "Changed")

    def test_other_agent_cannot_edit(self):
        lead_id = self.new_lead()["lead_id"]
        with self.assertRaises(PermissionError):
            editable_lead(self.conn, lead_id, self.agents[1]["id"])

    def test_company_admin_can_edit_company_lead(self):
        lead_id = self.new_lead()["lead_id"]
        target = self.agents[1]["id"]
        set_company_administrator(self.conn, actor_user_id=self.global_user_id,
                                  org_user_id=target, enabled=True)
        try:
            update_lead_details(self.conn, lead_id=lead_id, actor_org_user_id=target,
                password="TestPassword123", name="Admin correction", city="", context_full="",
                contacts=self.contact_payload(lead_id))
            self.assertEqual(self.conn.execute("SELECT name FROM leads WHERE id = ?", (lead_id,)).fetchone()["name"], "Admin correction")
        finally:
            set_company_administrator(self.conn, actor_user_id=self.global_user_id,
                                      org_user_id=target, enabled=False)

    def test_done_adds_contact_role_and_marks_stopped(self):
        created = self.new_lead()
        complete_action(self.conn, action_id=created["action_id"],
            actor_org_user_id=self.agents[0]["id"], completion_status="Oui",
            touchpoint_type="Appel", outcome="Refus", note="Spoke to colleague",
            new_contact_name="Colleague", new_contact_role="Decision maker",
            new_contact_phone="+237 600 000 000", create_next=False)
        touchpoint = self.conn.execute("SELECT contact_id FROM touchpoints WHERE action_id = ?", (created["action_id"],)).fetchone()
        contact = self.conn.execute("SELECT * FROM contacts WHERE id = ?", (touchpoint["contact_id"],)).fetchone()
        lead = self.conn.execute("SELECT churn_flag FROM leads WHERE id = ?", (created["lead_id"],)).fetchone()
        self.assertEqual((contact["full_name"], contact["role_title"], contact["phone_normalized"], lead["churn_flag"]),
                         ("Colleague", "Decision maker", "237600000000", 1))

    def test_completion_requires_role_and_reachable_channel_for_new_person(self):
        created = self.new_lead()
        with self.assertRaisesRegex(ValueError, "contact_required"):
            complete_action(self.conn, action_id=created["action_id"],
                actor_org_user_id=self.agents[0]["id"], completion_status="Oui",
                touchpoint_type="Appel", outcome="Intéressé", note="",
                new_contact_name="Person", new_contact_role="Director", create_next=False)
        self.assertEqual(self.conn.execute("SELECT status FROM actions WHERE id = ?",
            (created["action_id"],)).fetchone()["status"], "pending")

    def test_reactivation_links_reason_to_new_action(self):
        created = self.new_lead()
        complete_action(self.conn, action_id=created["action_id"], actor_org_user_id=self.agents[0]["id"],
            completion_status="Oui", touchpoint_type="Appel", outcome="Refus", note="Stopped", create_next=False)
        new_action = reactivate_lead(self.conn, lead_id=created["lead_id"],
            actor_org_user_id=self.agents[0]["id"], reason="They called back", title="Call again", due_date="2026-10-03")
        comments = list_comments_for_lead(self.conn, created["lead_id"])
        reason = next(row for row in comments if row["comment_type"] == "reactivation_reason")
        self.assertEqual((reason["action_id"], reason["action_title"], reason["body"]),
                         (new_action, "Call again", "They called back"))
        self.assertEqual(self.conn.execute("SELECT churn_flag FROM leads WHERE id = ?", (created["lead_id"],)).fetchone()["churn_flag"], 0)

    def test_active_lead_cannot_be_reactivated(self):
        created = self.new_lead()
        with self.assertRaisesRegex(ValueError, "already_active"):
            reactivate_lead(self.conn, lead_id=created["lead_id"], actor_org_user_id=self.agents[0]["id"],
                            reason="A reason", title="Call", due_date=None)

    def test_empty_reactivation_reason_is_rejected(self):
        created = self.new_lead()
        complete_action(self.conn, action_id=created["action_id"], actor_org_user_id=self.agents[0]["id"],
            completion_status="Oui", touchpoint_type="Appel", outcome="Refus", note="", create_next=False)
        with self.assertRaisesRegex(ValueError, "reason_required"):
            reactivate_lead(self.conn, lead_id=created["lead_id"], actor_org_user_id=self.agents[0]["id"],
                            reason=" ", title="Call", due_date=None)

    def test_action_comment_shows_action_title(self):
        created = self.new_lead()
        complete_action(self.conn, action_id=created["action_id"], actor_org_user_id=self.agents[0]["id"],
            completion_status="Oui", touchpoint_type="Appel", outcome="Intéressé", note="Positive note", create_next=False)
        comment = next(row for row in list_comments_for_lead(self.conn, created["lead_id"])
                       if row["comment_type"] == "action_note")
        self.assertTrue(comment["action_title"])

    def test_new_labels_exist_in_both_languages(self):
        for language in ("fr", "en"):
            for key in ("lead_manage.options", "lead_manage.reactivate", "admin.assign_company_admin"):
                self.assertNotEqual(t(key, language), key)


if __name__ == "__main__":
    unittest.main()
