# Journal de modifications NexStep

## 2026-10-08

- L’édition d’un agent est mise en évidence en haut de l’administration mobile ; les erreurs indiquent si l’API ou la migration Supabase attendue manque.
- Ajout d’« Actions d’équipe » pour les responsables d’équipe et administrateurs d’entreprise, sur Streamlit et Android : actions terminées classées de la plus récente à la plus ancienne, 20 par page, pagination par offset, contrôle serveur et requêtes limitées.
- Ajout d’un index PostgreSQL pour cette consultation, de traductions FR/EN, du guide utilisateur bilingue et de la version Android `1.0.8` (`versionCode 9`).
- Validation de 129 tests Python, 23 tests Deno, 919 contrôles statiques mobiles, audit FR/EN, typage TypeScript, Android Lint et compilation de l’APK. Aucune donnée de test n’a été laissée en base.

## 2026-10-03

- L’administrateur général scale.ag peut désormais modifier la fiche complète d’un agent depuis l’onglet « Utilisateurs » : identité, coordonnées, langue, état du compte, accès à l’entreprise et PIN facultatif.
- Le niveau d’autorité est choisi pour chaque entreprise : agent, responsable d’équipe ou administrateur d’entreprise. Les modifications sont atomiques, contrôlées côté serveur et auditées sans enregistrer le PIN.
- Même parcours dans l’administration Android, derrière le choix d’un agent ; ajout d’une fonction PostgreSQL privée dans la migration additive déjà prévue. Version mobile `1.0.7` (`versionCode 8`).
- Mise à jour des libellés français/anglais et du guide utilisateur bilingue.
- Contrôles validés : 120 tests Python, 15 tests Deno, audit des traductions, 883 contrôles mobiles, typage TypeScript, Android Lint et APK signé avec la clé Debug existante. Les bases de test temporaires ont été supprimées.

## 2026-10-02

- Ajout de l’attribution et du retrait du rôle administrateur d’entreprise par l’administrateur général scale.ag, avec contrôle serveur et audit.
- Modification discrète des leads et contacts existants dans le Lead Board : l’agent propriétaire ou l’administrateur d’entreprise confirme chaque édition par mot de passe.
- Ajout d’une personne à contacter, de sa fonction et d’au moins un moyen de la joindre dans les détails facultatifs de « Fait », avec rattachement à l’historique de l’action.
- Réactivation d’un lead arrêté par une nouvelle action et une raison enregistrée dans l’historique ; le churn est retiré lors de la relance.
- Affichage de l’action liée dans la liste des commentaires, sur Streamlit et Android.
- Ajout d’une migration SQL additive, de libellés FR/EN et de la documentation utilisateur ; Android passe en version `1.0.6` (`versionCode 7`).
- Vérification de 100 tests historiques et 13 tests d’intégration ciblés, 15 tests Deno, audit FR/EN, 847 contrôles mobiles, typage TypeScript, Android Lint et compilation APK. Les bases de test temporaires ont été supprimées.

## 2026-08-11

- Ajout d'une intelligence logiciste fondée sur une ontologie RDF/OWL : l'historique des actions, commentaires, résultats et échéances est transformé en signaux métier explicables.
- Ajout de suggestions conservatrices de churn pour les suivis durablement négatifs ou chronophages, avec protection systématique lorsqu'un signal positif récent existe.
- Ajout d'une suggestion d'action parmi les quatre choix déjà présents, sans nouvel écran, sans clic supplémentaire et sans modification automatique des données.
- Ajout des bibliothèques RDFLib et OWL-RL, de traductions françaises/anglaises, de contrôles dans la suite des 100 tests et de la documentation utilisateur bilingue.
- Portage des mêmes signaux et politiques ontologiques dans l’Edge Function mobile, avec suggestion expliquée dans le parcours Android sans décision automatique.
- Correction de la visibilité de l’administration mobile : le bouton Admin est désormais placé en deuxième position pour les comptes autorisés.
- Ajout de l’actualisation et d’un message d’erreur explicite dans la boîte mobile des demandes de réinitialisation, avec maintien de la portée globale du super-administrateur scale.ag.
- Ajout d’un formulaire de contact dans « Plus d’options » sur Streamlit et Android, afin d’enrichir un prospect à tout moment sans recréer sa fiche.
- Ajout d’une opération mobile contrôlée par l’entreprise et l’action, sans migration SQL ni modification du schéma Supabase.
- Passage de l’application Android en version `1.0.5` (`versionCode 6`).

## 2026-08-02

- Correction de la boîte de réinitialisation : le super-administrateur scale.ag voit et traite les demandes de toutes les entreprises, tandis que chaque administrateur local reste limité à la sienne.
- Ajout des coordonnées personnelles facultatives dans le menu « Aide » et de leur édition globale sécurisée dans l’onglet « Utilisateurs ».
- Alignement de la connexion Android sur Streamlit : identification par les deux PIN, puis saisie, création initiale ou changement du mot de passe selon le compte.
- Ajout d’une case bilingue pour afficher ou masquer les PIN et mots de passe saisis, sans les enregistrer sur le téléphone.
- Passage de l’application Android en version `1.0.2` (`versionCode 3`).

## 2026-07-30

- Remplacement complet de l’ancienne enveloppe WebView par une application Android autonome : aucun écran Streamlit ni navigateur intégré.
- Ajout des écrans Android natifs bilingues de connexion, prochaine action, parcours de clôture, création de prospect avec plusieurs contacts, Lead Board, liste d’actions et administration.
- Ajout d’une API Supabase Edge Function dédiée qui réutilise les PIN, mots de passe, rôles et sessions révocables existants sans exposer PostgreSQL au téléphone.
- Ajout de cinq fonctions PostgreSQL privées et transactionnelles via une migration strictement additive, sans modification ni suppression des tables et données en production.
- Chiffrement de la session mobile avec Android Keystore; aucun PIN ni mot de passe n’est conservé sur le téléphone.
- Ajout des exports Excel, ICS avec rappel la veille et sauvegardes JSON autorisées, ainsi que des liens téléphone, Agenda et scale.ag.
- Blocage Gradle de `DATABASE_URL`, `APP_PIN_PEPPER`, des clés secrètes Supabase, des URL PostgreSQL et de toute réintroduction de WebView dans l’APK.
- Ajout d’un guide de déploiement Supabase actualisé et d’un script bilingue de compilation/signature utilisant uniquement l’URL publique et la clé Publishable.
- Validation réussie de 705 contrôles statiques, 7 tests cryptographiques Deno, 100 tests Python de non-régression, contrôle TypeScript, compilation de l’APK Android natif et Android Lint sans erreur ni avertissement avec l’API 34 de diagnostic.
- Remplacement de l’écran de diagnostic bloquant par une configuration mobile bilingue : URL publique préremplie, saisie de la clé Publishable, validation stricte, test de l’Edge Function et mémorisation locale des seules valeurs publiques.
- Ajout d’un accès à la configuration depuis la connexion et passage de l’application Android en version `1.0.1` (`versionCode 2`).
- Ajout d’un déploiement PowerShell guidé du backend mobile Supabase et correction du répertoire d’exécution du CLI afin d’éviter l’écran « Edge Function non déployée ».

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
- Ajout pour le super administrateur d’une sauvegarde de secours globale couvrant les 19 tables, toutes les entreprises, tous les utilisateurs, les données métier, journaux, sessions et empreintes d’authentification.
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
