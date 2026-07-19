"""One hundred automated checks for the NexStep MVP."""

from __future__ import annotations

import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["NEXSTEP_FAST_HASH"] = "1"

from database.connection import (
    DatabaseConfigurationError,
    adapt_query_for_postgres,
    get_connection,
    normalize_postgres_url,
)
from services.action_service import complete_action, get_next_action, list_actions, resolve_org_user_by_pin, transfer_action
from services.auth_service import identify_by_pins, password_mode, set_user_password, verify_user_password
from services.comment_service import add_comment, list_comments_for_lead, recent_comments_for_lead, search_comments
from services.lead_service import get_lead_detail, get_primary_contact, team_summary, unassigned_leads_count
from services.migration_service import migrate_sqlite_to_postgres
from services.new_lead_service import create_lead_with_first_action
from services.seed_service import AGENT_PINS, LEGACY_COMMENTS, ensure_seed_data, seed_validation_counts
from utils.dates import excel_serial_to_date, format_date, parse_date
from utils.i18n import load_locale, t
from utils.security import hash_password, hash_pin, pin_lookup, verify_password, verify_pin
from utils.text import new_id, normalize_name, slugify, stable_id
from utils.urgency import urgency_color


TABLES = [
    "organizations",
    "users",
    "organization_users",
    "pipeline_stages",
    "lead_statuses",
    "client_categories",
    "action_types",
    "leads",
    "contacts",
    "actions",
    "touchpoints",
    "transfers",
    "comments",
    "import_batches",
    "import_rows",
    "auth_attempts",
    "audit_logs",
]

EXPECTED_COUNTS = {
    "organizations": 2,
    "agents": 5,
    "leads": 78,
    "actions": 76,
    "actions_with_due_date": 20,
    "contacts_with_name": 39,
    "contacts_with_phone": 6,
    "unassigned_leads": 42,
    "legacy_comments": 22,
    "import_rows": 78,
}

CHECKS = []


def check(name):
    def decorator(func):
        CHECKS.append((name, func))
        return func

    return decorator


class NexStepCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_root = ROOT / "tmp" / "tests"
        cls.tmp_root.mkdir(parents=True, exist_ok=True)
        cls.db_path = cls.tmp_root / f"nexstep_test_{uuid.uuid4().hex}.db"
        os.environ["NEXSTEP_DATABASE_PATH"] = str(cls.db_path)
        cls.conn = get_connection(cls.db_path)
        ensure_seed_data(cls.conn)
        cls.org = cls.conn.execute("SELECT * FROM organizations WHERE slug = 'les-confiotes'").fetchone()
        cls.admin_org = cls.conn.execute("SELECT * FROM organizations WHERE slug = 'scale-ag'").fetchone()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        cls.db_path.unlink(missing_ok=True)
        os.environ.pop("NEXSTEP_DATABASE_PATH", None)
        os.environ.pop("NEXSTEP_FAST_HASH", None)

    def fresh_conn(self):
        path = self.tmp_root / f"fresh_{uuid.uuid4().hex}.db"
        self.addCleanup(lambda p=path: p.unlink(missing_ok=True))
        conn = get_connection(path)
        self.addCleanup(conn.close)
        ensure_seed_data(conn)
        return conn

    def agent_org_user(self, conn, display_name: str):
        return conn.execute(
            """
            SELECT ou.*, u.display_name
            FROM organization_users ou
            JOIN users u ON u.id = ou.user_id
            JOIN organizations o ON o.id = ou.organization_id
            WHERE o.slug = 'les-confiotes' AND u.display_name = ?
            """,
            (display_name,),
        ).fetchone()


for table_name in TABLES:
    @check(f"table_{table_name}_exists")
    def _(self, table_name=table_name):
        row = self.conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,)).fetchone()
        self.assertIsNotNone(row)


for key, expected in EXPECTED_COUNTS.items():
    @check(f"seed_count_{key}")
    def _(self, key=key, expected=expected):
        self.assertEqual(seed_validation_counts(self.conn)[key], expected)


for agent_name, pin in AGENT_PINS.items():
    @check(f"agent_identifies_{agent_name}")
    def _(self, pin=pin):
        result = identify_by_pins(self.conn, "lesconfiotes1991", pin)
        self.assertTrue(result.ok)


@check("admin_initial_identifies")
def _(self):
    result = identify_by_pins(self.conn, "0015", "0015")
    self.assertTrue(result.ok)
    self.assertEqual(result.org_user["role"], "super_admin")


@check("bad_pin_is_generic")
def _(self):
    result = identify_by_pins(self.conn, "wrong", "wrong")
    self.assertFalse(result.ok)
    self.assertEqual(result.message_key, "login.invalid_credentials")


@check("agent_requires_password_setup")
def _(self):
    result = identify_by_pins(self.conn, "lesconfiotes1991", "0001")
    self.assertEqual(password_mode(result.user), "setup")


@check("admin_requires_initial_password_change")
def _(self):
    result = identify_by_pins(self.conn, "0015", "0015")
    self.assertEqual(password_mode(result.user), "change")


@check("set_password_allows_login")
def _(self):
    conn = self.fresh_conn()
    result = identify_by_pins(conn, "lesconfiotes1991", "0001")
    set_user_password(conn, result.user["id"], "secret")
    user = conn.execute("SELECT * FROM users WHERE id = ?", (result.user["id"],)).fetchone()
    self.assertTrue(verify_user_password(user, "secret"))


@check("pin_lookup_is_stable")
def _(self):
    self.assertEqual(pin_lookup(" 0001 "), pin_lookup("0001"))


@check("pin_hashes_are_salted")
def _(self):
    self.assertNotEqual(hash_pin("0001"), hash_pin("0001"))


@check("password_hashes_are_salted")
def _(self):
    self.assertNotEqual(hash_password("secret"), hash_password("secret"))


@check("wrong_password_fails")
def _(self):
    hashed = hash_password("secret")
    self.assertFalse(verify_password("other", hashed))


@check("pin_verification_accepts_correct_pin")
def _(self):
    hashed = hash_pin("0001")
    self.assertTrue(verify_pin("0001", hashed))


@check("normalize_duplicate_names")
def _(self):
    self.assertEqual(normalize_name("BLACK AND WHITE"), normalize_name("Black-and White"))


@check("slugify_accents")
def _(self):
    self.assertEqual(slugify("Les Confiotes!"), "les-confiotes")


@check("stable_id_is_deterministic")
def _(self):
    self.assertEqual(stable_id("x", "y"), stable_id("x", "y"))


@check("new_id_is_unique")
def _(self):
    self.assertNotEqual(new_id(), new_id())


@check("excel_serial_conversion")
def _(self):
    self.assertEqual(excel_serial_to_date(46204), "2026-07-01")


@check("format_date_empty")
def _(self):
    self.assertEqual(format_date(None), "—")


@check("parse_date_invalid")
def _(self):
    self.assertIsNone(parse_date("not a date"))


URGENCY_CASES = [
    ("red", "2026-07-03"),
    ("yellow", "2026-07-04"),
    ("yellow_future", "2026-07-10"),
    ("green", "2026-07-11"),
    ("blue", "2026-08-05"),
    ("gray", None),
]

for name, due_date in URGENCY_CASES:
    @check(f"urgency_{name}")
    def _(self, name=name, due_date=due_date):
        expected = "yellow" if name == "yellow_future" else name
        self.assertEqual(urgency_color(due_date, parse_date("2026-07-04")), expected)


@check("joel_next_action_exists")
def _(self):
    ou = self.agent_org_user(self.conn, "Joël")
    action = get_next_action(self.conn, self.org["id"], ou["id"])
    self.assertIsNotNone(action)


@check("joel_next_action_is_oldest_due")
def _(self):
    ou = self.agent_org_user(self.conn, "Joël")
    action = get_next_action(self.conn, self.org["id"], ou["id"])
    self.assertEqual(action["due_date"], "2026-05-16")


@check("list_actions_contains_urgency")
def _(self):
    ou = self.agent_org_user(self.conn, "Joël")
    actions = list_actions(self.conn, self.org["id"], org_user_id=ou["id"])
    self.assertIn("urgency_color", actions[0])


@check("list_actions_excludes_done_by_default")
def _(self):
    conn = self.fresh_conn()
    ou = self.agent_org_user(conn, "Joël")
    action = get_next_action(conn, self.org["id"], ou["id"])
    complete_action(conn, action_id=action["id"], actor_org_user_id=ou["id"], completion_status="Oui", touchpoint_type="Appel", outcome="À relancer", note="Test", create_next=False)
    actions = list_actions(conn, self.org["id"], org_user_id=ou["id"])
    self.assertNotIn(action["id"], [item["id"] for item in actions])


@check("quick_comment_creates_row")
def _(self):
    conn = self.fresh_conn()
    ou = self.agent_org_user(conn, "Joël")
    action = get_next_action(conn, self.org["id"], ou["id"])
    add_comment(conn, organization_id=action["organization_id"], lead_id=action["lead_id"], action_id=action["id"], org_user_id=ou["id"], body="Commentaire test")
    conn.commit()
    self.assertTrue(any(c["body"] == "Commentaire test" for c in list_comments_for_lead(conn, action["lead_id"])))


@check("recent_comments_limit")
def _(self):
    lead = self.conn.execute("SELECT id FROM leads WHERE legacy_row_number = 5").fetchone()
    self.assertLessEqual(len(recent_comments_for_lead(self.conn, lead["id"], limit=2)), 2)


@check("comment_search_finds_legacy")
def _(self):
    results = search_comments(self.conn, self.org["id"], "WhatsApp")
    self.assertGreaterEqual(len(results), 1)


@check("complete_action_marks_done")
def _(self):
    conn = self.fresh_conn()
    ou = self.agent_org_user(conn, "Joël")
    action = get_next_action(conn, self.org["id"], ou["id"])
    complete_action(conn, action_id=action["id"], actor_org_user_id=ou["id"], completion_status="Oui", touchpoint_type="Appel", outcome="Intéressé", note="OK", create_next=False)
    row = conn.execute("SELECT status FROM actions WHERE id = ?", (action["id"],)).fetchone()
    self.assertEqual(row["status"], "done")


@check("complete_action_creates_touchpoint")
def _(self):
    conn = self.fresh_conn()
    ou = self.agent_org_user(conn, "Joël")
    action = get_next_action(conn, self.org["id"], ou["id"])
    result = complete_action(conn, action_id=action["id"], actor_org_user_id=ou["id"], completion_status="Oui", touchpoint_type="Appel", outcome="Intéressé", note="OK", create_next=False)
    self.assertIsNotNone(result["touchpoint_id"])


@check("complete_action_creates_comment")
def _(self):
    conn = self.fresh_conn()
    ou = self.agent_org_user(conn, "Joël")
    action = get_next_action(conn, self.org["id"], ou["id"])
    complete_action(conn, action_id=action["id"], actor_org_user_id=ou["id"], completion_status="Oui", touchpoint_type="Appel", outcome="Intéressé", note="Compte rendu test", create_next=False)
    comments = list_comments_for_lead(conn, action["lead_id"])
    self.assertTrue(any(c["comment_type"] == "action_note" for c in comments))


@check("complete_action_creates_next_action")
def _(self):
    conn = self.fresh_conn()
    ou = self.agent_org_user(conn, "Joël")
    action = get_next_action(conn, self.org["id"], ou["id"])
    result = complete_action(conn, action_id=action["id"], actor_org_user_id=ou["id"], completion_status="Oui", touchpoint_type="Appel", outcome="À relancer", note="OK", create_next=True, next_due_date="2026-07-08", next_action_type="Appel", next_title="Relancer", next_comment="Suite")
    self.assertIsNotNone(result["next_action_id"])


@check("transfer_marks_original_transferred")
def _(self):
    conn = self.fresh_conn()
    ou = self.agent_org_user(conn, "Joël")
    action = get_next_action(conn, self.org["id"], ou["id"])
    transfer_action(conn, action_id=action["id"], actor_org_user_id=ou["id"], target_agent_pin="0000", transfer_note="Israel connaît le contact")
    row = conn.execute("SELECT status FROM actions WHERE id = ?", (action["id"],)).fetchone()
    self.assertEqual(row["status"], "transferred")


@check("transfer_creates_target_action")
def _(self):
    conn = self.fresh_conn()
    ou = self.agent_org_user(conn, "Joël")
    action = get_next_action(conn, self.org["id"], ou["id"])
    result = transfer_action(conn, action_id=action["id"], actor_org_user_id=ou["id"], target_agent_pin="0000", transfer_note="À reprendre")
    self.assertIsNotNone(conn.execute("SELECT id FROM actions WHERE id = ?", (result["new_action_id"],)).fetchone())


@check("transfer_comment_visible")
def _(self):
    conn = self.fresh_conn()
    ou = self.agent_org_user(conn, "Joël")
    action = get_next_action(conn, self.org["id"], ou["id"])
    transfer_action(conn, action_id=action["id"], actor_org_user_id=ou["id"], target_agent_pin="0000", transfer_note="À reprendre")
    comments = list_comments_for_lead(conn, action["lead_id"])
    self.assertTrue(any(c["comment_type"] == "transfer_note" for c in comments))


@check("resolve_valid_agent_pin")
def _(self):
    self.assertEqual(resolve_org_user_by_pin(self.conn, self.org["id"], "0001")["display_name"], "Joël")


@check("resolve_invalid_agent_pin")
def _(self):
    self.assertIsNone(resolve_org_user_by_pin(self.conn, self.org["id"], "9999"))


@check("team_summary_has_five_agents")
def _(self):
    self.assertEqual(len(team_summary(self.conn, self.org["id"])), 5)


@check("team_summary_has_red_actions")
def _(self):
    self.assertGreater(sum(item["urgencies"]["red"] for item in team_summary(self.conn, self.org["id"])), 0)


@check("unassigned_leads_count")
def _(self):
    self.assertEqual(unassigned_leads_count(self.conn, self.org["id"]), 42)


@check("lead_detail_black_and_white")
def _(self):
    lead = self.conn.execute("SELECT id FROM leads WHERE legacy_row_number = 5").fetchone()
    self.assertEqual(get_lead_detail(self.conn, lead["id"])["name"], "BLACK AND WHITE")


@check("primary_contact_exists_for_first_lead")
def _(self):
    lead = self.conn.execute("SELECT id FROM leads WHERE legacy_row_number = 5").fetchone()
    self.assertIsNotNone(get_primary_contact(self.conn, lead["id"]))


@check("legacy_comments_have_source_column_a")
def _(self):
    count = self.conn.execute("SELECT COUNT(*) AS count FROM comments WHERE comment_type = 'legacy_excel_a' AND source_column = 'a'").fetchone()["count"]
    self.assertEqual(count, 22)


@check("blank_legacy_rows_have_no_legacy_comment")
def _(self):
    commented_rows = {
        row["legacy_row_number"] - 4
        for row in self.conn.execute(
            "SELECT l.legacy_row_number FROM comments c JOIN leads l ON l.id = c.lead_id WHERE c.comment_type = 'legacy_excel_a'"
        )
    }
    self.assertNotIn(18, commented_rows)


@check("duplicate_group_has_two_black_and_white")
def _(self):
    count = self.conn.execute("SELECT COUNT(*) AS count FROM leads WHERE possible_duplicate_group = 'black-and-white'").fetchone()["count"]
    self.assertEqual(count, 2)


@check("migration_dry_run_counts_tables")
def _(self):
    report = migrate_sqlite_to_postgres(str(self.db_path), dry_run=True)
    self.assertEqual(report.table_counts["leads"], 78)


@check("new_lead_requires_name")
def _(self):
    conn = self.fresh_conn()
    ou = self.agent_org_user(conn, "Joël")
    before = conn.execute("SELECT COUNT(*) AS count FROM leads").fetchone()["count"]
    with self.assertRaises(ValueError):
        create_lead_with_first_action(
            conn,
            organization_id=self.org["id"],
            actor_org_user_id=ou["id"],
            lead_name=" ",
        )
    after = conn.execute("SELECT COUNT(*) AS count FROM leads").fetchone()["count"]
    self.assertEqual(before, after)


@check("new_lead_creates_owned_lead")
def _(self):
    conn = self.fresh_conn()
    ou = self.agent_org_user(conn, "Joël")
    result = create_lead_with_first_action(
        conn,
        organization_id=self.org["id"],
        actor_org_user_id=ou["id"],
        lead_name=f"Test lead {uuid.uuid4().hex}",
        category_name="Restaurant",
    )
    lead = conn.execute("SELECT * FROM leads WHERE id = ?", (result["lead_id"],)).fetchone()
    self.assertEqual(lead["owner_org_user_id"], ou["id"])


@check("new_lead_creates_first_action")
def _(self):
    conn = self.fresh_conn()
    ou = self.agent_org_user(conn, "Joël")
    result = create_lead_with_first_action(
        conn,
        organization_id=self.org["id"],
        actor_org_user_id=ou["id"],
        lead_name=f"Action lead {uuid.uuid4().hex}",
        action_type_name="Appel",
        action_title="Premier contact test",
        due_date="2026-07-06",
    )
    action = conn.execute("SELECT * FROM actions WHERE id = ?", (result["action_id"],)).fetchone()
    self.assertEqual((action["status"], action["assigned_to_org_user_id"], action["due_date"]), ("pending", ou["id"], "2026-07-06"))


@check("new_lead_creates_contact")
def _(self):
    conn = self.fresh_conn()
    ou = self.agent_org_user(conn, "Joël")
    result = create_lead_with_first_action(
        conn,
        organization_id=self.org["id"],
        actor_org_user_id=ou["id"],
        lead_name=f"Contact lead {uuid.uuid4().hex}",
        contact_name="Marie Test",
        phone_raw="+237 699 000 111",
        channel_notes="WhatsApp",
    )
    contact = conn.execute("SELECT * FROM contacts WHERE id = ?", (result["contact_id"],)).fetchone()
    self.assertEqual(contact["phone_normalized"], "237699000111")


@check("new_lead_creates_comment")
def _(self):
    conn = self.fresh_conn()
    ou = self.agent_org_user(conn, "Joël")
    result = create_lead_with_first_action(
        conn,
        organization_id=self.org["id"],
        actor_org_user_id=ou["id"],
        lead_name=f"Comment lead {uuid.uuid4().hex}",
        context_note="Rencontré au salon.",
        action_details="Rappeler demain.",
    )
    comment = conn.execute("SELECT * FROM comments WHERE id = ?", (result["comment_id"],)).fetchone()
    self.assertIn("Rappeler demain", comment["body"])


@check("new_lead_marks_possible_duplicate")
def _(self):
    conn = self.fresh_conn()
    ou = self.agent_org_user(conn, "Joël")
    result = create_lead_with_first_action(
        conn,
        organization_id=self.org["id"],
        actor_org_user_id=ou["id"],
        lead_name="Black and White",
    )
    lead = conn.execute("SELECT possible_duplicate_group FROM leads WHERE id = ?", (result["lead_id"],)).fetchone()
    self.assertEqual(lead["possible_duplicate_group"], "black-and-white")


@check("postgres_url_normalization")
def _(self):
    self.assertEqual(
        normalize_postgres_url("postgres://user:secret@example.test/db"),
        "postgresql://user:secret@example.test/db",
    )
    self.assertEqual(
        normalize_postgres_url("postgresql+psycopg://user:secret@example.test/db"),
        "postgresql://user:secret@example.test/db",
    )
    with self.assertRaises(DatabaseConfigurationError):
        normalize_postgres_url("sqlite:///local.db")


@check("postgres_query_adapter_preserves_literals")
def _(self):
    query = "SELECT ? AS value, '?' AS literal, \"?\" AS identifier, 'it''s ?' AS escaped"
    self.assertEqual(
        adapt_query_for_postgres(query),
        "SELECT %s AS value, '?' AS literal, \"?\" AS identifier, 'it''s ?' AS escaped",
    )


@check("cloud_requires_database_url")
def _(self):
    with mock.patch.dict(os.environ, {"APP_ENV": "cloud", "DATABASE_URL": ""}, clear=False):
        with self.assertRaises(DatabaseConfigurationError):
            get_connection()


@check("supabase_security_covers_all_tables")
def _(self):
    security_sql = (ROOT / "database" / "supabase_security.sql").read_text(encoding="utf-8")
    for table in TABLES:
        self.assertIn(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY", security_sql)
    self.assertIn("FROM anon, authenticated", security_sql)


I18N_KEYS = [
    "login.company_pin",
    "nav.new_lead",
    "new_lead.title",
    "new_lead.success",
    "spinner.new_lead",
]

for language in ("fr", "en"):
    for key in I18N_KEYS:
        @check(f"i18n_{language}_{key}")
        def _(self, language=language, key=key):
            self.assertNotEqual(t(key, language), key)


def _make_test(func):
    def test(self):
        return func(self)

    return test


assert len(CHECKS) == 100, f"Expected exactly 100 generated checks, got {len(CHECKS)}"

for index, (name, func) in enumerate(CHECKS, start=1):
    setattr(NexStepCore, f"test_{index:03d}_{name}", _make_test(func))


if __name__ == "__main__":
    unittest.main(verbosity=2)
