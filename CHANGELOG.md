# Journal de modifications NexStep

## 2026-07-28

- Remplacement des fiches prospects techniques et de la carte équipe par un Lead Board unique, filtrable et sélectionnable, avec contacts, actions et commentaires en langage utilisateur.
- Suppression du menu « Plus » devenu inutile; l’administration apparaît directement pour les rôles autorisés.
- Correction du cache de traduction afin que les nouveaux libellés, dont l’accès rapide sur l’écran de connexion, soient rechargés après un déploiement.
- Ajout d’un audit exhaustif des clés et variables de traduction FR/EN, avec correction des statuts d’action manquants.
- Ajout d’une compatibilité de rechargement Streamlit pour éviter le crash du menu après un déploiement à chaud.
- Les formulaires de commentaire refusent désormais un texte vide avec un message traduit au lieu de lever une erreur.
- Ajout du récapitulatif de tous les membres de l’entreprise et du filtre multi-agents selon les droits existants.
- Ajout de l’export Excel du Lead Board filtré pour chaque agent.
- Extension de la création guidée à cinq contacts par prospect, sans changement du schéma des contacts.
- Ajout des liens Google Agenda et des fichiers ICS avec rappel un jour avant l’échéance.
- Ajout de fichiers d’accès personnels révocables, sans PIN ni mot de passe, la couche native de cookies Streamlit étant en lecture seule.
- Ajout du workflow de réinitialisation de mot de passe approuvé ou refusé dans l’application par un administrateur d’entreprise.
- Ajout d’une archive ZIP de CSV pour exporter et remplacer atomiquement les données métier d’une entreprise, avec trois confirmations du PIN entreprise et une confirmation du mot de passe administrateur.
- Ajout d’une migration Supabase strictement additive pour `auth_sessions` et `password_reset_requests`, avec RLS et retrait des droits publics.
- Mise à jour des catalogues FR/EN, du guide utilisateur bilingue, du guide de migration et des 100 tests automatisés.

## 2026-07-19

- Remplacement de l'écran agent principal par un parcours guidé affichant une seule action et une seule décision à la fois.
- Ajout d'une clôture en quatre étapes simples: résultat, suite, échéance et confirmation.
- Ajout du report temporaire « Plus tard » sans modification des données, ainsi que de l'appel direct depuis un numéro de téléphone sur mobile.
- Transformation de la création d'un lead en création guidée de prospect, avec détails facultatifs repliés.
- Réduction de la navigation quotidienne à « À faire maintenant », « Ajouter un prospect » et « Mes actions »; les vues avancées restent sous « Plus » selon les droits existants.
- Remplacement du jargon « lead » par « prospect » dans l'interface agent française et anglaise, sans modifier les noms de tables ni les services métier.
- Conservation intégrale de la base de données, de la connexion Supabase/PostgreSQL, des PIN, mots de passe, rôles et accès administrateur.
- Refonte du guide utilisateur HTML bilingue pour décrire les nouveaux parcours guidés.
- Ajout du lien `https://scale-ag.tech/` sur le logo scale.ag dans l'application et le guide utilisateur.

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
