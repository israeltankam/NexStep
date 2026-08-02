# NexStep Mobile

NexStep Mobile est une véritable application Android native. Elle ne charge ni
Streamlit ni une page Web : connexion, prochaine action, création de prospect,
Lead Board, actions et administration sont des écrans Android intégrés à l’APK.

Les données restent communes avec l’application Web :

```text
Application Android native
  -> HTTPS
Supabase Edge Function nexstep-mobile-api
  -> accès serveur protégé
Base PostgreSQL Supabase existante
```

## Sécurité : aucune URL PostgreSQL dans l’APK

Ne jamais fournir `DATABASE_URL`, le mot de passe PostgreSQL, une clé
`sb_secret_...`, une clé `service_role` ou `APP_PIN_PEPPER` à Gradle. Un APK
peut être décompilé.

Deux valeurs publiques seulement sont compilées dans l’application :

- l’URL publique du projet, par exemple
  `https://PROJECT_REF.supabase.co`;
- la clé **Publishable**, qui commence par `sb_publishable_`.

Elles se trouvent dans Supabase, **Project Settings > API Keys**. Elles sont
prévues pour les applications mobiles. La base reste protégée par RLS et le
téléphone ne l’interroge jamais directement.

Un APK Debug construit sans clé affiche désormais un formulaire utilisable :
l’URL du projet NexStep est préremplie, l’administrateur colle la clé
Publishable une fois, puis l’application vérifie l’Edge Function avant de
continuer. Un APK Release destiné aux agents intègre ces deux valeurs et
n’affiche donc pas ce formulaire.

Le jeton de session NexStep est chiffré avec Android Keystore. Les PIN et le mot
de passe ne sont pas enregistrés sur le téléphone.

## 1. Activer le serveur mobile dans Supabase

Cette opération se fait une seule fois. La procédure complète se trouve dans
[`supabase/README.md`](supabase/README.md).

En résumé :

1. exécuter le SQL additif
   `supabase/database/20260730_native_mobile_transactions.sql` dans le SQL
   Editor du projet ;
2. ajouter à l’Edge Function le secret `APP_PIN_PEPPER`, avec exactement la
   même valeur que dans Streamlit Cloud ;
3. déployer `nexstep-mobile-api` avec le Supabase CLI ;
4. tester l’opération `health`.

La migration crée uniquement cinq fonctions SQL privées. Elle ne recrée,
n’efface et ne modifie aucune table ni aucune donnée existante.

## 2. Préparer Android sous Windows

1. Installer Android Studio et son JDK.
2. Dans **SDK Manager**, installer Android SDK Platform 36 et les Build-Tools.
3. Ouvrir le dossier `mobile_app` dans Android Studio et attendre la
   synchronisation Gradle.

Le premier build peut télécharger Gradle et le plugin Android.

## 3. Construire l’APK de test

Depuis PowerShell, dans `NexStep\mobile_app`, un APK de test configurable sur
le téléphone peut être construit sans renseigner la clé :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_android.ps1 `
  -Configuration Debug `
  -CompileSdk 34 `
  -TargetSdk 34
```

Pour intégrer immédiatement la configuration publique :

```powershell
$env:NEXSTEP_SUPABASE_URL = "https://PROJECT_REF.supabase.co"
$env:NEXSTEP_SUPABASE_PUBLISHABLE_KEY = "sb_publishable_VOTRE_CLE_PUBLIQUE"

powershell -ExecutionPolicy Bypass -File .\scripts\build_android.ps1 `
  -Configuration Debug `
  -SupabaseUrl $env:NEXSTEP_SUPABASE_URL `
  -PublishableKey $env:NEXSTEP_SUPABASE_PUBLISHABLE_KEY
```

Le script exécute plus de 100 contrôles, Android Lint et la compilation. L’APK
est créé ici :

```text
app/build/outputs/apk/debug/app-debug.apk
```

Installation sur un téléphone connecté en USB :

```powershell
adb install -r .\app\build\outputs\apk\debug\app-debug.apk
```

## 4. Construire l’APK final signé

Créer une clé de signature une seule fois, hors du dépôt Git :

```powershell
keytool -genkeypair -v -keystore C:\chemin-prive\nexstep-release.jks `
  -alias nexstep -keyalg RSA -keysize 4096 -validity 10000
```

Puis définir les informations de signature dans la session PowerShell :

```powershell
$env:NEXSTEP_KEYSTORE_PATH = "C:\chemin-prive\nexstep-release.jks"
$env:NEXSTEP_KEY_ALIAS = "nexstep"

$secureStorePassword = Read-Host "Mot de passe du keystore" -AsSecureString
$env:NEXSTEP_KEYSTORE_PASSWORD = [System.Net.NetworkCredential]::new(
  "",
  $secureStorePassword
).Password

$secureKeyPassword = Read-Host "Mot de passe de la clé" -AsSecureString
$env:NEXSTEP_KEY_PASSWORD = [System.Net.NetworkCredential]::new(
  "",
  $secureKeyPassword
).Password

powershell -ExecutionPolicy Bypass -File .\scripts\build_android.ps1 `
  -Configuration Release `
  -SupabaseUrl $env:NEXSTEP_SUPABASE_URL `
  -PublishableKey $env:NEXSTEP_SUPABASE_PUBLISHABLE_KEY
```

Résultat :

```text
app/build/outputs/apk/release/app-release.apk
```

Le keystore, ses mots de passe, les clés privées Supabase et les secrets restent
hors de Git.

## 5. Recette sur téléphone

1. Vérifier le français et l’anglais.
2. Si la configuration apparaît, coller la clé Publishable puis toucher
   **Vérifier et continuer**.
3. Se connecter avec les PIN et mot de passe habituels.
4. Fermer et rouvrir l’application : la session chiffrée doit être reprise.
5. Créer un prospect avec plusieurs contacts et une première action.
6. Terminer, commenter et transférer une action.
7. Vérifier le Lead Board, ses filtres et son export Excel.
8. Exporter une action vers Agenda ou en fichier ICS.
9. Pour un administrateur, traiter une demande de mot de passe et télécharger
   la sauvegarde autorisée.
10. Pour le super administrateur, vérifier que la sauvegarde globale exige de
   nouveau son mot de passe.
11. Vérifier qu’un agent ne voit ni les données d’une autre entreprise ni les
    commandes d’administration.

## Mises à jour

- Une modification d’écran Android nécessite un nouvel APK.
- Une modification de l’Edge Function nécessite son redéploiement, mais pas
  forcément un nouvel APK si son contrat JSON reste compatible.
- Une évolution SQL doit rester une migration additive contrôlée.
- Une évolution Streamlit n’est pas automatiquement répercutée dans le mobile :
  ce sont désormais deux interfaces indépendantes partageant le même métier et
  la même base.

---

## English

NexStep Mobile is a real native Android application. It does not open or embed
Streamlit. Its Android screens call a protected Supabase Edge Function, which
uses the existing PostgreSQL database server-side.

Never put `DATABASE_URL`, a PostgreSQL password, `APP_PIN_PEPPER`, a
`service_role` key or an `sb_secret_...` key in the APK. Compile only the public
project URL and the public `sb_publishable_...` key:

```powershell
$env:NEXSTEP_SUPABASE_URL = "https://PROJECT_REF.supabase.co"
$env:NEXSTEP_SUPABASE_PUBLISHABLE_KEY = "sb_publishable_YOUR_PUBLIC_KEY"

powershell -ExecutionPolicy Bypass -File .\scripts\build_android.ps1 `
  -Configuration Debug `
  -SupabaseUrl $env:NEXSTEP_SUPABASE_URL `
  -PublishableKey $env:NEXSTEP_SUPABASE_PUBLISHABLE_KEY
```

Follow [`supabase/README.md`](supabase/README.md) once to install the additive
SQL helpers, configure the server-side pepper and deploy the Edge Function.
