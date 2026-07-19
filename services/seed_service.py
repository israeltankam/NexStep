"""Idempotent seed data for the NexStep MVP.

The Les Confiotes dataset is recreated from the specification appendix. It is
not a replacement for the future Excel importer; it gives the pilot a working
database and gives tests stable acceptance counts.
"""

from __future__ import annotations

import json
import sqlite3

from database.repository import fetch_one, insert
from database.schema import create_schema
from services.comment_service import add_comment
from utils.dates import utcnow_iso
from utils.security import hash_password, hash_pin, pin_lookup
from utils.text import normalize_name, slugify, stable_id
from utils.urgency import urgency_color


STAGES = ["Nouveau lead", "Premier contact", "Discovery", "Nurture", "Offre", "Client gagné", "Perdu / Churn", "Non renseigné"]
STATUSES = ["Nouveau", "Hot", "Actif", "À traiter cette semaine", "Churn", "Non renseigné"]
CATEGORIES = ["CHR", "Hotel", "Restaurant", "Bar / Lounge"]
ACTION_TYPES = [
    "Appel",
    "Appel, Opener",
    "Closing",
    "Dégustation",
    "Dégustation / No Discovery Call",
    "Discovery Call / Entrainer Barman",
    "Double appel + WhatsApp/VN",
    "Envoyer contenu valeur hebdo",
    "Envoyer Guide ; Offre ; Carte Saison",
    "Offre",
    "Présentation Produits",
    "RDV",
    "Relance douce",
    "Suivi client J+7 / rachat",
    "Trouver entrée",
    "Autre",
]

AGENT_PINS = {"Israël": "0000", "Joël": "0001", "Macho": "0002", "Ro": "0003", "Ene": "0004"}
ASSIGNMENTS = {
    1: "Joël",
    2: "Israël",
    3: "Joël",
    4: "Joël",
    5: "Joël",
    6: "Joël",
    7: "Israël",
    8: "Israël",
    9: "Israël",
    10: "Joël",
    11: "Israël",
    12: "Joël",
    13: "Israël",
    14: "Israël",
    15: "Ene",
    16: "Joël",
    17: "Israël",
    18: "Macho",
    19: "Ro",
    23: "Ro",
    24: "Ene",
    25: "Ro",
    26: "Joël",
    27: "Israël",
    41: "Joël",
    44: "Ene",
    46: "Ene",
    47: "Ene",
    59: "Joël",
    60: "Joël",
    61: "Joël",
    74: "Joël",
    75: "Joël",
    76: "Joël",
    77: "Joël",
    78: "Joël",
}

LEAD_NAMES = [
    "BLACK AND WHITE",
    "Kings' Corner",
    "Saphir Group",
    "Vault Bar Restaurant",
    "Villa Magnum",
    "Les Perroquets Bali",
    "Le Bun est tr",
    "Lounge Atangana",
    "Calvin Dama",
    "Wandafull Terrasse",
    "Rooftop Yaoundé",
    "50 Nuances de Grey",
    "Ethnic Restaurant",
    "DON PEDRO",
    "White House",
    "Santa Lucia",
    "HOTEL NOUBOU BONAPRISO",
    "L'Ovalie",
    "Mystic Bantu",
    "Soya Restaurant",
    "O'SAN",
    "La Crêperie",
    "Jimmy Wings",
    "St Germain",
    "Impala",
    "The Forest",
    "Lagoon",
    "Marquise",
    "K Hôtel",
    "Hilton",
    "Cascade St. David",
    "Akwa Palace",
    "Ô LA'KAM",
    "Geneva Hotel",
    "LION'S GATE",
    "LE TCHO'O",
    "JOHEN Résidence",
    "O'HAIRA WALLET",
    "BOLONGI",
    "LE FLAMANT",
    "L'Atelier",
    "Starland Hotel",
    "GRAND PALACE CASINO",
    "JJ QUEST / BEST WESTERN / LE GRILLADIN / SAGA AFRICA",
    "WDC Appart Hotel Buea",
    "ONOMO PALACE",
    "JJ QUEST",
    "PROCURE DES MISSIONS",
    "BLACK AND WHITE",
    "50 NUANCES DE GREY",
    "FAYA HOTEL",
    "AROMATIC STORE",
    "SAGA AFRICA",
    "LE GRILLADIN",
    "Tagidor",
    "Sawa Hotel",
    "Bubble Bar",
    "K Hotel",
    "The Yard",
    "RESTAURANT LE C",
    "ZINGANA",
    "XO BAR",
    "Royal Palace Casino",
    "Restaurant LE CONTINENT 237",
    "Ô Mulatako",
    "MAXIMS DE PARIS",
    "LE BISTROT LATIN",
    "LA MARINA YOUPWE",
    "Krystal Palace",
    "EL MIMOSA",
    "BODEGA",
    "BEST WESTERN HOTEL",
    "BE BOP",
    "White Smoke Bar 237",
    "Stardust",
    "Sky Bar",
    "Lynk privé Bar & Lounge",
    "Les Palétuviers",
]

DUE_DATES = {
    1: "2026-05-19",
    3: "2026-06-10",
    4: "2026-06-17",
    5: "2026-06-08",
    6: "2026-06-10",
    7: "2026-05-19",
    10: "2026-05-17",
    11: "2026-05-16",
    12: "2026-06-17",
    13: "2026-04-29",
    14: "2026-04-29",
    15: "2026-04-29",
    16: "2026-06-03",
    17: "2026-06-09",
    26: "2026-05-16",
    74: "2026-06-17",
    75: "2026-06-17",
    76: "2026-06-17",
    77: "2026-06-17",
    78: "2026-06-17",
}

NO_ACTION_ROWS = {8, 9}

LEGACY_COMMENTS = {
    1: "Ils ont goûté les produits. Le barman trouve que certains sirops ne sont pas de bonne qualité. Il faut y aller avec Ro.",
    2: "Relance de Jean-Marie pour Kings' Corner. Ouverture officielle retardée pour problème de liquidité.",
    3: "RDV pris le 19/06/2026. Ils ont aimé passion et coco. Le barman veut passer commande; il faut y aller aujourd'hui.",
    4: "Ro et Joel sont passés. Dégustation au bar, objection prix, questions sur l'offre et les comparaisons.",
    5: "Réception puis barman rencontrés. Objection prix du PDG; WhatsApp envoyé. Prévoir passage tôt vers 18h.",
    6: "Les barmen ont reconnu l'équipe. Très bon échange, intérêt pour l'offre et relance prévue en juillet.",
    7: "Le Burger Bar n'est pas intéressé; le chef veut que les barmen se débrouillent.",
    8: "Intéressés par l'offre et les liqueurs. À revoir en face pour en parler.",
    10: "Les barmen apprécient les produits. Manager difficile à joindre; Ene doit y aller.",
    11: "Les gens du Rooftop Yaoundé ont aimé les sirops. Clarifier comment activer la commande.",
    12: "Ne sont pas intéressés, travaillent déjà avec des fournisseurs agréés.",
    13: "Documentation WhatsApp non lue. Relancer directement et proposer une dégustation.",
    14: "En attente des mixologues. Le patron n'est plus au Cameroun; Christian doit repasser.",
    15: "Ene a discuté avec lui. Il veut passer par ses barmans; contact Yaoundé potentiellement utile.",
    16: "Ils ont adoré passion et coco. Le barman conseille de programmer une dégustation avec la responsable.",
    17: "Offre envoyée. Israël doit relancer le NOUBOU pour demander des updates.",
    41: "Elle va parler à leur superviseur. Joel a proposé de relancer à 14h.",
    61: "La décision dépend de ses supérieurs. Elle demande l'offre par WhatsApp pour transmission.",
    74: "Ne décroche pas mais échanges WhatsApp; ils disent revenir.",
    75: "RDV pris le 18/06/2026 à 16h. Préparer sirop passion.",
    76: "Dès qu'il a entendu qu'on fournit des sirops, il a dit ne pas être intéressé.",
    77: "Ne décroche ni en direct ni sur WhatsApp. Message laissé.",
}


def _now() -> str:
    return utcnow_iso()


def _insert_ignore(conn: sqlite3.Connection, table: str, values: dict[str, object]) -> None:
    columns = list(values.keys())
    placeholders = ", ".join("?" for _ in columns)
    conn.execute(
        # Supported by both modern SQLite and PostgreSQL. This preserves user
        # changes because seed rows are inserted only when their IDs are absent.
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
        [values[column] for column in columns],
    )


def _ensure_organization(conn: sqlite3.Connection, name: str, slug: str, pin: str, **extra: object) -> sqlite3.Row:
    now = _now()
    _insert_ignore(
        conn,
        "organizations",
        {
            "id": stable_id("organization", slug),
            "name": name,
            "slug": slug,
            "display_name": extra.get("display_name", name),
            "company_pin_lookup": pin_lookup(pin),
            "company_pin_hash": hash_pin(pin),
            "default_language": extra.get("default_language", "fr"),
            "client_label": extra.get("client_label", "Client"),
            "is_active": 1,
            "created_at": now,
            "updated_at": now,
        },
    )
    return fetch_one(conn, "SELECT * FROM organizations WHERE slug = ?", (slug,))


def _ensure_user(conn: sqlite3.Connection, display_name: str, *, password: str | None = None, global_admin: bool = False) -> sqlite3.Row:
    now = _now()
    user_id = stable_id("user", display_name)
    _insert_ignore(
        conn,
        "users",
        {
            "id": user_id,
            "display_name": display_name,
            "email": None,
            "phone": None,
            "password_hash": hash_password(password) if password else None,
            "password_set_at": now if password else None,
            "must_change_password": 1 if password else 0,
            "preferred_language": "fr",
            "is_active": 1,
            "is_global_admin": 1 if global_admin else 0,
            "created_at": now,
            "updated_at": now,
        },
    )
    return fetch_one(conn, "SELECT * FROM users WHERE id = ?", (user_id,))


def _ensure_org_user(conn: sqlite3.Connection, organization_id: str, user_id: str, agent_pin: str, role: str, can_view_team: bool = True) -> sqlite3.Row:
    now = _now()
    org_user_id = stable_id("organization_user", f"{organization_id}:{user_id}")
    _insert_ignore(
        conn,
        "organization_users",
        {
            "id": org_user_id,
            "organization_id": organization_id,
            "user_id": user_id,
            "agent_pin_lookup": pin_lookup(agent_pin),
            "agent_pin_hash": hash_pin(agent_pin),
            "role": role,
            "can_view_team": 1 if can_view_team else 0,
            "is_active": 1,
            "created_at": now,
            "updated_at": now,
        },
    )
    return fetch_one(conn, "SELECT * FROM organization_users WHERE id = ?", (org_user_id,))


def _ensure_reference(conn: sqlite3.Connection, table: str, organization_id: str, name: str, position: int) -> str:
    now = _now()
    row_id = stable_id(table, f"{organization_id}:{name}")
    values: dict[str, object] = {
        "id": row_id,
        "organization_id": organization_id,
        "name": name,
        "position": position,
        "is_active": 1,
        "created_at": now,
    }
    if table == "pipeline_stages":
        values["is_won"] = 1 if name == "Client gagné" else 0
        values["is_lost"] = 1 if name == "Perdu / Churn" else 0
    if table == "lead_statuses":
        values["color_name"] = "gray"
    if table == "client_categories":
        values.pop("position", None)
        values["description"] = None
    _insert_ignore(conn, table, values)
    return row_id


def _status_for(row_number: int) -> str:
    explicit = {
        1: "Actif",
        2: "Hot",
        3: "Hot",
        4: "Nouveau",
        5: "Hot",
        6: "Hot",
        7: "Churn",
        8: "Non renseigné",
        9: "Non renseigné",
        10: "Actif",
        11: "Actif",
        12: "Churn",
        13: "Actif",
        14: "À traiter cette semaine",
        15: "Actif",
        16: "Churn",
        17: "Hot",
        18: "Actif",
        19: "Churn",
        61: "Actif",
        74: "Nouveau",
        75: "Nouveau",
        76: "Churn",
        77: "Nouveau",
        78: "Nouveau",
    }
    if row_number in explicit:
        return explicit[row_number]
    if 20 <= row_number <= 60:
        return "Churn"
    if 62 <= row_number <= 73:
        return "Actif"
    return "Non renseigné"


def _stage_for(row_number: int) -> str:
    explicit = {
        1: "Offre",
        2: "Premier contact",
        3: "Offre",
        4: "Offre",
        5: "Nurture",
        6: "Discovery",
        7: "Premier contact",
        8: "Premier contact",
        9: "Nurture",
        10: "Nurture",
        11: "Nurture",
        12: "Nurture",
        13: "Nouveau lead",
        14: "Nouveau lead",
        15: "Nouveau lead",
        16: "Nouveau lead",
        17: "Nouveau lead",
        18: "Nouveau lead",
        19: "Nurture",
        20: "Client gagné",
        21: "Nurture",
        22: "Offre",
        23: "Nouveau lead",
        24: "Nurture",
        25: "Discovery",
        26: "Nurture",
        27: "Client gagné",
        28: "Client gagné",
        57: "Perdu / Churn",
    }
    if row_number in explicit:
        return explicit[row_number]
    if 29 <= row_number <= 43:
        return "Premier contact"
    if 44 <= row_number <= 60:
        return "Nurture"
    return "Non renseigné"


def _action_title_for(row_number: int) -> str | None:
    if row_number in NO_ACTION_ROWS:
        return None
    if row_number in {1, 5, 10, 16}:
        return "Dégustation / No Discovery Call"
    if row_number in {2, 3}:
        return "Closing"
    if row_number in {4, 12, 74, 75, 76, 77, 78}:
        return "Appel, Opener"
    if row_number in {6, 29, 34, 37, 38, 39, 40, 44, 45, 46, 48, 51, 58, 59, 60, 62, 63, 64, 65, 68, 72, 73}:
        return "Appel"
    if row_number in {7}:
        return "Présentation Produits"
    if row_number in {13}:
        return "Envoyer Guide ; Offre ; Carte Saison"
    if row_number in {14}:
        return "RDV"
    if row_number in {26}:
        return "Discovery Call / Entrainer Barman"
    if row_number in {30, 31, 43, 54}:
        return "Suivi client J+7 / rachat"
    if row_number in {50, 52, 53, 69}:
        return "Double appel + WhatsApp/VN"
    if row_number in {57}:
        return "Relance douce"
    if row_number in {20}:
        return "Trouver entrée"
    return "Envoyer contenu valeur hebdo"


def _score_for(row_number: int) -> float:
    explicit = {1: 92, 3: 87, 4: 82, 5: 38, 6: 50, 7: 42, 8: 42, 9: 38, 10: 38, 11: 38, 12: 38, 13: 32, 14: 32}
    if row_number in explicit:
        return float(explicit[row_number])
    if 15 <= row_number <= 18:
        return 32.0
    return 0.0


def _category_for(row_number: int) -> str:
    if any(word in LEAD_NAMES[row_number - 1].casefold() for word in ["hotel", "hôtel", "palace"]):
        return "Hotel"
    if any(word in LEAD_NAMES[row_number - 1].casefold() for word in ["restaurant", "grilladin", "bistrot"]):
        return "Restaurant"
    if any(word in LEAD_NAMES[row_number - 1].casefold() for word in ["bar", "lounge"]):
        return "Bar / Lounge"
    return "CHR"


def ensure_seed_data(conn: sqlite3.Connection) -> None:
    """Create schema and seed admin plus Les Confiotes data if missing."""

    create_schema(conn)
    scale = _ensure_organization(conn, "scale.ag", "scale-ag", "0015", display_name="scale.ag")
    admin = _ensure_user(conn, "Admin scale.ag", password="0015", global_admin=True)
    _ensure_org_user(conn, scale["id"], admin["id"], "0015", "super_admin", True)

    org = _ensure_organization(conn, "Les Confiotes", "les-confiotes", "lesconfiotes1991", display_name="Les Confiotes")
    agent_org_users: dict[str, sqlite3.Row] = {}
    for name, pin in AGENT_PINS.items():
        user = _ensure_user(conn, name)
        agent_org_users[name] = _ensure_org_user(conn, org["id"], user["id"], pin, "agent", True)

    for position, name in enumerate(STAGES, start=1):
        _ensure_reference(conn, "pipeline_stages", org["id"], name, position)
    for position, name in enumerate(STATUSES, start=1):
        _ensure_reference(conn, "lead_statuses", org["id"], name, position)
    for position, name in enumerate(CATEGORIES, start=1):
        _ensure_reference(conn, "client_categories", org["id"], name, position)
    for position, name in enumerate(ACTION_TYPES, start=1):
        _ensure_reference(conn, "action_types", org["id"], name, position)

    existing = fetch_one(conn, "SELECT COUNT(*) AS count FROM leads WHERE organization_id = ?", (org["id"],))
    if existing and int(existing["count"]) >= 78:
        conn.commit()
        return

    batch_id = stable_id("import_batch", "les-confiotes-seed")
    _insert_ignore(
        conn,
        "import_batches",
        {
            "id": batch_id,
            "organization_id": org["id"],
            "source_filename": "Les_Confiotes CRM Sales.xlsx",
            "imported_by_user_id": admin["id"],
            "row_count": 78,
            "imported_at": _now(),
            "status": "completed",
            "notes": "Préremplissage initial issu du cahier des charges NexStep.",
        },
    )

    for row_number, lead_name in enumerate(LEAD_NAMES, start=1):
        owner_name = ASSIGNMENTS.get(row_number)
        owner_id = agent_org_users[owner_name]["id"] if owner_name else None
        stage_id = stable_id("pipeline_stages", f"{org['id']}:{_stage_for(row_number)}")
        status_id = stable_id("lead_statuses", f"{org['id']}:{_status_for(row_number)}")
        category_id = stable_id("client_categories", f"{org['id']}:{_category_for(row_number)}")
        duplicate_group = "black-and-white" if normalize_name(lead_name) == "black and white" else None
        lead_id = stable_id("lead", f"les-confiotes:{row_number}")
        raw = {
            "Rang": row_number,
            "Lead": lead_name,
            "Responsable": owner_name or "À assigner",
            "Urgence": _status_for(row_number),
            "Etape": _stage_for(row_number),
            "Prochaine relance": DUE_DATES.get(row_number),
            "Action": _action_title_for(row_number),
            "a": LEGACY_COMMENTS.get(row_number, ""),
        }
        _insert_ignore(
            conn,
            "leads",
            {
                "id": lead_id,
                "organization_id": org["id"],
                "name": lead_name,
                "normalized_name": normalize_name(lead_name),
                "owner_org_user_id": owner_id,
                "stage_id": stage_id,
                "status_id": status_id,
                "category_id": category_id,
                "city": None,
                "address": None,
                "latitude": None,
                "longitude": None,
                "score": _score_for(row_number),
                "source": "Excel legacy",
                "source_detail": "Pipeline",
                "obstacle": None,
                "context_full": f"Contexte legacy conservé pour {lead_name}.",
                "prioritization_reason": "Priorisation héritée du fichier Excel.",
                "churn_flag": 1 if _status_for(row_number) == "Churn" else 0,
                "legacy_rank": float(row_number),
                "legacy_row_number": row_number + 4,
                "legacy_age_days": None,
                "legacy_touchpoint_count": 0,
                "legacy_fields_json": json.dumps(raw, ensure_ascii=False),
                "possible_duplicate_group": duplicate_group,
                "is_archived": 0,
                "created_at": _now(),
                "updated_at": _now(),
            },
        )
        if row_number <= 39:
            _insert_ignore(
                conn,
                "contacts",
                {
                    "id": stable_id("contact", f"les-confiotes:{row_number}"),
                    "lead_id": lead_id,
                    "full_name": f"Contact {lead_name}",
                    "role_title": "Contact principal",
                    "phone_raw": f"+237 690 000 0{row_number}" if row_number <= 6 else None,
                    "phone_normalized": f"2376900000{row_number}" if row_number <= 6 else None,
                    "email": None,
                    "whatsapp": None,
                    "channel_notes": "Téléphone / WhatsApp" if row_number <= 6 else "Canal à confirmer",
                    "is_primary": 1,
                    "created_at": _now(),
                    "updated_at": _now(),
                },
            )
        action_title = _action_title_for(row_number)
        if action_title:
            action_type_id = stable_id("action_types", f"{org['id']}:{action_title}") if action_title in ACTION_TYPES else stable_id("action_types", f"{org['id']}:Autre")
            _insert_ignore(
                conn,
                "actions",
                {
                    "id": stable_id("action", f"les-confiotes:{row_number}"),
                    "organization_id": org["id"],
                    "lead_id": lead_id,
                    "assigned_to_org_user_id": owner_id,
                    "created_by_org_user_id": None,
                    "action_type_id": action_type_id,
                    "title": action_title,
                    "details": raw["Action"],
                    "due_date": DUE_DATES.get(row_number),
                    "status": "pending",
                    "urgency_color_cache": urgency_color(DUE_DATES.get(row_number)),
                    "completed_at": None,
                    "completed_by_org_user_id": None,
                    "completion_note": None,
                    "transferred_to_org_user_id": None,
                    "previous_action_id": None,
                    "created_at": _now(),
                    "updated_at": _now(),
                },
            )
        _insert_ignore(
            conn,
            "import_rows",
            {
                "id": stable_id("import_row", f"les-confiotes:{row_number}"),
                "import_batch_id": batch_id,
                "lead_id": lead_id,
                "excel_sheet": "Pipeline",
                "excel_row_number": row_number + 4,
                "raw_json": json.dumps(raw, ensure_ascii=False),
                "import_status": "imported",
                "error_message": None,
                "created_at": _now(),
            },
        )
        if row_number in LEGACY_COMMENTS:
            existing_comment = fetch_one(
                conn,
                "SELECT id FROM comments WHERE lead_id = ? AND comment_type = 'legacy_excel_a'",
                (lead_id,),
            )
            if not existing_comment:
                add_comment(
                    conn,
                    organization_id=org["id"],
                    lead_id=lead_id,
                    body=LEGACY_COMMENTS[row_number],
                    comment_type="legacy_excel_a",
                    visibility="team",
                    source="excel_import",
                    source_column="a",
                    is_system_import=True,
                )
    conn.commit()


def seed_validation_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return the acceptance counts listed in the specification patch."""

    org = fetch_one(conn, "SELECT * FROM organizations WHERE slug = 'les-confiotes'")
    if not org:
        return {}
    queries = {
        "organizations": "SELECT COUNT(*) AS count FROM organizations",
        "agents": "SELECT COUNT(*) AS count FROM organization_users ou JOIN users u ON u.id = ou.user_id WHERE ou.organization_id = ? AND ou.role = 'agent'",
        "leads": "SELECT COUNT(*) AS count FROM leads WHERE organization_id = ?",
        "actions": "SELECT COUNT(*) AS count FROM actions WHERE organization_id = ?",
        "actions_with_due_date": "SELECT COUNT(*) AS count FROM actions WHERE organization_id = ? AND due_date IS NOT NULL",
        "contacts_with_name": "SELECT COUNT(*) AS count FROM contacts c JOIN leads l ON l.id = c.lead_id WHERE l.organization_id = ? AND c.full_name IS NOT NULL",
        "contacts_with_phone": "SELECT COUNT(*) AS count FROM contacts c JOIN leads l ON l.id = c.lead_id WHERE l.organization_id = ? AND c.phone_raw IS NOT NULL",
        "unassigned_leads": "SELECT COUNT(*) AS count FROM leads WHERE organization_id = ? AND owner_org_user_id IS NULL",
        "legacy_comments": "SELECT COUNT(*) AS count FROM comments WHERE organization_id = ? AND comment_type = 'legacy_excel_a'",
        "import_rows": "SELECT COUNT(*) AS count FROM import_rows ir JOIN import_batches ib ON ib.id = ir.import_batch_id WHERE ib.organization_id = ?",
    }
    counts: dict[str, int] = {}
    for key, query in queries.items():
        params = () if key == "organizations" else (org["id"],)
        row = fetch_one(conn, query, params)
        counts[key] = int(row["count"] if row else 0)
    return counts
