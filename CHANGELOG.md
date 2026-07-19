# Journal de modifications NexStep

## 2026-07-16

- Correction critique de la persistance cloud: l'application utilise désormais réellement `DATABASE_URL` avec PostgreSQL/Supabase au lieu d'écrire systématiquement dans SQLite.
- Ajout d'un mode cloud fermé par défaut: `APP_ENV=cloud` interdit tout fallback silencieux vers le disque éphémère de Streamlit Cloud si `DATABASE_URL` manque.
- Ajout d'un adaptateur PostgreSQL pour conserver les services existants, avec lignes dictionnaires, SSL obligatoire, délai de connexion et compatibilité avec les poolers Supabase.
- Ajout du fichier `database/supabase_security.sql` qui active RLS sur les 17 tables et retire les privilèges Data API aux rôles `anon` et `authenticated`.
- Ajout du script standalone `scripts/secure_supabase.py` pour contrôler ou appliquer le verrouillage Supabase sans afficher les secrets.
- Mise à jour bilingue du guide de migration avec la procédure Session pooler, les secrets Streamlit, le correctif RLS et le test de persistance après redémarrage.
- Mise à jour de la suite de 100 tests pour couvrir le branchement PostgreSQL et les garde-fous cloud/Supabase.

## 2026-07-05

- Ajout de la page agent `Nouveau lead` pour créer un lead et sa première action en une seule opération.
- Ajout du service transactionnel `create_lead_with_first_action`, avec contact optionnel, commentaire optionnel, assignation à l'agent connecté et détection simple de doublon.
- Correction de la lecture des catégories client, qui n'ont pas de colonne `position` dans le schéma.
- Ajout des textes bilingues FR/EN, du spinner dédié et de la mise à jour du guide utilisateur.

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
