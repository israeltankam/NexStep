# Journal de modifications NexStep

## 2026-07-04

- Création de l'application Streamlit NexStep dans `NexStep`.
- Déplacement des logos vers `assets/logos/` et intégration dans le login et la sidebar.
- Ajout d'une base SQLite locale, d'un schéma compatible migration PostgreSQL et du seed initial scale.ag / Les Confiotes.
- Ajout du login par PIN entreprise + PIN agent, puis mot de passe, avec hachage et journalisation des tentatives.
- Ajout des pages agent: prochaine action, toutes mes actions, fiche client et carte opérationnelle d'équipe.
- Ajout de la console `scale.ag Admin Console`.
- Intégration du patch commentaires: colonne Excel `a`, `comment_type=legacy_excel_a`, badges, recherche et historique complet.
- Ajout des catalogues bilingues FR/EN.
- Ajout du guide utilisateur HTML bilingue.
- Ajout d'une suite de 100 tests automatisés via `unittest`.
- Remplacement des libellés d'urgence visibles par des formulations métier FR/EN, sans changer les codes couleurs.
- Correction renforcée des filtres d'urgence: les options visibles utilisent directement les libellés métier, les codes couleur restent internes.
- Correction de l'affichage des logos via conteneurs HTML avec `object-fit: contain` pour éviter le tronquage.
- Ajout d'un téléchargement du guide utilisateur depuis le login et la sidebar.
- Ajout d'un guide HTML de migration SQLite vers PostgreSQL pour Streamlit Cloud.
- Transformation du script `scripts/migrate_sqlite_to_postgres.py` en migration standalone avec mode `--dry-run` et mode réel `--apply`.
- Clarification du guide de migration: remplacement explicite du placeholder Supabase `[YOUR-PASSWORD]`, usage de `--postgres-url`, puis stockage dans `DATABASE_URL` côté Streamlit Cloud.
