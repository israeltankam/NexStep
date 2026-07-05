"""Shared constants kept out of presentation code."""

ROLES = ("super_admin", "company_admin", "manager", "agent")
COMMENT_TYPES = (
    "general",
    "action_note",
    "transfer_note",
    "next_action_note",
    "legacy_excel_a",
    "legacy_context",
    "admin_note",
)
COMMENT_VISIBILITIES = ("team", "manager", "admin")

TOUCHPOINT_TYPES = (
    "Appel",
    "WhatsApp",
    "Visite",
    "Dégustation",
    "Email",
    "Rendez-vous",
    "Relance douce",
    "Closing",
    "Autre",
)

OUTCOMES = (
    "Intéressé",
    "À relancer",
    "Pas disponible",
    "Refus",
    "Commande probable",
    "Commande confirmée",
    "Perdu",
    "Autre",
)

ACTION_DONE_OPTIONS = ("Oui", "Non", "Partiellement")
