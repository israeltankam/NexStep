"""Team activity permissions and offset pagination on disposable SQLite data."""

from __future__ import annotations

import os
import tempfile
import unittest
import uuid
from pathlib import Path

os.environ["NEXSTEP_FAST_HASH"] = "1"

from database.connection import get_connection
from services.admin_service import create_organization, create_user, link_user_to_organization
from services.seed_service import ensure_seed_data
from services.team_actions_service import PAGE_SIZE, list_team_actions


class TeamActionsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=Path(__file__).parents[1] / "tmp")
        self.conn = get_connection(Path(self.temporary.name) / "team.db")
        ensure_seed_data(self.conn)
        self.global_id = self.conn.execute(
            "SELECT id FROM users WHERE is_global_admin = 1 LIMIT 1").fetchone()["id"]
        self.org_id = create_organization(self.conn, name="Team Tests", slug="team-tests",
            company_pin="CompanyPIN", default_language="fr", client_label="Client",
            is_active=True, actor_user_id=self.global_id)
        self.links = {}
        for role in ("agent", "manager", "company_admin"):
            user_id = create_user(self.conn, display_name=role.title(), email=None,
                phone=None, preferred_language="fr", is_active=True,
                actor_user_id=self.global_id)
            self.links[role] = link_user_to_organization(self.conn,
                organization_id=self.org_id, user_id=user_id, agent_pin=role + "PIN",
                role=role, can_view_team=True, actor_user_id=self.global_id)
        self.lead_id = uuid.uuid4().hex
        self.conn.execute("""INSERT INTO leads
            (id,organization_id,name,normalized_name,owner_org_user_id,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?)""", (self.lead_id, self.org_id, "Test prospect",
                "test prospect", self.links["agent"], "2026-10-08", "2026-10-08"))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temporary.cleanup()

    def add_action(self, number: int, *, status: str = "done", organization_id: str | None = None,
                   lead_id: str | None = None, completed_at: str | None = None):
        action_id = f"test-action-{number:03d}-{uuid.uuid4().hex[:6]}"
        organization_id = organization_id or self.org_id
        self.conn.execute("""INSERT INTO actions
            (id,organization_id,lead_id,title,status,completed_at,
             completed_by_org_user_id,completion_note,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", (action_id, organization_id,
                lead_id or self.lead_id, f"Action {number}", status,
                completed_at if completed_at is not None else f"2026-10-08T12:{number:02d}:00+00:00",
                self.links["agent"] if organization_id == self.org_id else None,
                f"Note {number}", "2026-10-08", "2026-10-08"))
        self.conn.commit()
        return action_id

    def page(self, role="manager", offset=0):
        return list_team_actions(self.conn, organization_id=self.org_id,
            actor_org_user_id=self.links[role], offset=offset)

    def test_manager_sees_only_first_twenty_and_lookahead(self):
        for number in range(25):
            self.add_action(number)
        page = self.page()
        self.assertEqual((len(page.actions), page.offset, page.has_more), (PAGE_SIZE, 0, True))
        self.assertEqual(page.actions[0]["title"], "Action 24")
        self.assertEqual(page.actions[-1]["title"], "Action 5")
        self.assertEqual(page.actions[0]["completed_by_name"], "Agent")

    def test_second_page_has_no_duplicates_and_no_more(self):
        for number in range(25):
            self.add_action(number)
        first, second = self.page(offset=0), self.page(offset=20)
        self.assertEqual(len(second.actions), 5)
        self.assertFalse(second.has_more)
        self.assertTrue({row["id"] for row in first.actions}.isdisjoint(
            {row["id"] for row in second.actions}))

    def test_company_admin_can_read(self):
        self.add_action(1)
        self.assertEqual(len(self.page("company_admin").actions), 1)

    def test_agent_with_team_visibility_still_cannot_read(self):
        self.add_action(1)
        with self.assertRaises(PermissionError):
            self.page("agent")

    def test_disabled_manager_cannot_read(self):
        self.conn.execute("UPDATE organization_users SET is_active = 0 WHERE id = ?",
                          (self.links["manager"],))
        self.conn.commit()
        with self.assertRaises(PermissionError):
            self.page()

    def test_wrong_company_is_forbidden(self):
        seed_org = self.conn.execute("SELECT id FROM organizations WHERE id <> ? LIMIT 1",
                                     (self.org_id,)).fetchone()["id"]
        with self.assertRaises(PermissionError):
            list_team_actions(self.conn, organization_id=seed_org,
                actor_org_user_id=self.links["manager"])

    def test_pending_actions_and_other_company_are_absent(self):
        self.add_action(1)
        self.add_action(2, status="pending")
        seed_org = self.conn.execute("SELECT id FROM organizations WHERE id <> ? LIMIT 1",
                                     (self.org_id,)).fetchone()["id"]
        foreign_lead = uuid.uuid4().hex
        self.conn.execute("""INSERT INTO leads
            (id,organization_id,name,normalized_name,created_at,updated_at)
            VALUES (?,?,?,?,?,?)""", (foreign_lead, seed_org, "Other lead", "other lead",
                                      "2026-10-08", "2026-10-08"))
        self.add_action(3, organization_id=seed_org, lead_id=foreign_lead)
        self.assertEqual([row["title"] for row in self.page().actions], ["Action 1"])

    def test_invalid_offsets_are_rejected(self):
        for value in (-20, 1.5, True):
            with self.assertRaisesRegex(ValueError, "invalid_offset"):
                self.page(offset=value)

    def test_equal_completion_times_have_stable_id_order(self):
        first = self.add_action(1, completed_at="2026-10-08T12:00:00+00:00")
        second = self.add_action(2, completed_at="2026-10-08T12:00:00+00:00")
        self.assertEqual([row["id"] for row in self.page().actions],
                         sorted((first, second), reverse=True))


if __name__ == "__main__":
    unittest.main()
