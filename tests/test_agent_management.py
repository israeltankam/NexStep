"""Integration checks for complete agent editing; all data is temporary."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ["NEXSTEP_FAST_HASH"] = "1"

from database.connection import get_connection
from services.admin_service import create_organization, link_user_to_organization
from services.agent_management_service import list_editable_agents, update_agent
from services.seed_service import ensure_seed_data
from utils.security import verify_pin


class AgentManagementTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=Path(__file__).parents[1] / "tmp")
        self.conn = get_connection(Path(self.temporary.name) / "agents.db")
        ensure_seed_data(self.conn)
        self.global_id = self.conn.execute(
            "SELECT id FROM users WHERE is_global_admin = 1 LIMIT 1").fetchone()["id"]
        self.agent = self.conn.execute("""
            SELECT ou.id, ou.user_id, ou.organization_id FROM organization_users ou
            JOIN users u ON u.id = ou.user_id WHERE u.is_global_admin = 0 LIMIT 1
        """).fetchone()

    def tearDown(self):
        self.conn.close()
        self.temporary.cleanup()

    def edit(self, **changes):
        data = dict(actor_user_id=self.global_id, org_user_id=self.agent["id"],
                    display_name="Agent modifié", email="agent@example.com", phone="+237 123",
                    preferred_language="en", role="company_admin", can_view_team=False,
                    account_active=True, link_active=True, new_pin="")
        data.update(changes)
        update_agent(self.conn, **data)

    def test_global_admin_edits_all_profile_fields_and_role(self):
        self.edit(new_pin="FreshPin904")
        user = self.conn.execute("SELECT * FROM users WHERE id = ?", (self.agent["user_id"],)).fetchone()
        link = self.conn.execute("SELECT * FROM organization_users WHERE id = ?", (self.agent["id"],)).fetchone()
        self.assertEqual((user["display_name"], user["email"], user["phone"], user["preferred_language"]),
                         ("Agent modifié", "agent@example.com", "+237 123", "en"))
        self.assertEqual((link["role"], link["can_view_team"]), ("company_admin", 1))
        self.assertTrue(verify_pin("FreshPin904", link["agent_pin_hash"]))

    def test_role_is_company_specific(self):
        second_org = create_organization(self.conn, name="Another company", slug="another-company",
            company_pin="OtherCompanyPin", default_language="en", client_label="Client",
            is_active=True, actor_user_id=self.global_id)
        second_link = link_user_to_organization(self.conn, organization_id=second_org,
            user_id=self.agent["user_id"], agent_pin="OtherAgentPin", role="agent",
            can_view_team=False, actor_user_id=self.global_id)
        self.edit(role="company_admin")
        self.assertEqual(self.conn.execute("SELECT role FROM organization_users WHERE id = ?",
                                           (second_link,)).fetchone()["role"], "agent")

    def test_global_admin_can_disable_and_reenable_agent(self):
        self.edit(account_active=False, link_active=False)
        self.assertEqual(self.conn.execute("SELECT is_active FROM users WHERE id = ?",
                                           (self.agent["user_id"],)).fetchone()["is_active"], 0)
        self.assertEqual(self.conn.execute("SELECT is_active FROM organization_users WHERE id = ?",
                                           (self.agent["id"],)).fetchone()["is_active"], 0)
        self.assertIn(self.agent["id"], [row["org_user_id"] for row in
                                      list_editable_agents(self.conn, actor_user_id=self.global_id)])
        self.edit(account_active=True, link_active=True)

    def test_non_global_admin_cannot_edit_or_list(self):
        with self.assertRaises(PermissionError):
            self.edit(actor_user_id=self.agent["user_id"])
        with self.assertRaises(PermissionError):
            list_editable_agents(self.conn, actor_user_id=self.agent["user_id"])

    def test_invalid_fields_leave_everything_unchanged(self):
        before = self.conn.execute("SELECT display_name FROM users WHERE id = ?",
                                   (self.agent["user_id"],)).fetchone()["display_name"]
        for bad in ({"display_name": ""}, {"email": "bad"}, {"role": "super_admin"},
                    {"preferred_language": "xx"}):
            with self.assertRaises(ValueError):
                self.edit(**bad)
        after = self.conn.execute("SELECT display_name FROM users WHERE id = ?",
                                  (self.agent["user_id"],)).fetchone()["display_name"]
        self.assertEqual(before, after)

    def test_duplicate_company_pin_is_rejected(self):
        another = self.conn.execute("""
            SELECT id FROM organization_users WHERE organization_id = ? AND id <> ? LIMIT 1
        """, (self.agent["organization_id"], self.agent["id"])).fetchone()
        if not another:
            self.skipTest("seed has only one company agent")
        # The lookup is seeded, so querying it is enough to prove collision handling.
        from utils.security import pin_lookup
        self.conn.execute("UPDATE organization_users SET agent_pin_lookup = ? WHERE id = ?",
                          (pin_lookup("AlreadyUsed"), another["id"]))
        with self.assertRaisesRegex(ValueError, "duplicate_pin"):
            self.edit(new_pin="AlreadyUsed")

    def test_audit_contains_no_contact_or_pin(self):
        self.edit(new_pin="PrivatePin904")
        audit = self.conn.execute("SELECT after_json FROM audit_logs WHERE action = 'update_agent' ORDER BY created_at DESC LIMIT 1").fetchone()
        self.assertNotIn("PrivatePin904", audit["after_json"])
        self.assertNotIn("agent@example.com", audit["after_json"])


if __name__ == "__main__":
    unittest.main()
