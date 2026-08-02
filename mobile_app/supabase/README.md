# Déployer le serveur de NexStep Mobile

Cette procédure connecte l’application Android native à la base Supabase déjà
utilisée en production. Elle ne remplace aucune table et n’efface aucune donnée.

## Ce qui va où

| Valeur | Emplacement | Dans l’APK |
|---|---|---|
| URL publique `https://PROJECT_REF.supabase.co` | Build Android | Oui |
| Clé `sb_publishable_...` | Build Android | Oui |
| `APP_PIN_PEPPER` existant | Secrets de l’Edge Function | Non |
| Clé `sb_secret_...` / `service_role` | Fournie automatiquement à l’Edge Function | Non |
| `DATABASE_URL` / mot de passe PostgreSQL | Inutile pour l’APK et l’Edge Function | Non |

## 1. Exécuter la migration additive

1. Ouvrir le projet dans le Dashboard Supabase.
2. Ouvrir **SQL Editor** puis créer une nouvelle requête.
3. Ouvrir localement
   `mobile_app/supabase/database/20260730_native_mobile_transactions.sql`.
4. Coller tout le contenu dans le SQL Editor et toucher **Run** une seule fois.

Le script est transactionnel et idempotent. Il crée ou met à jour les fonctions
privées suivantes :

- `nexstep_mobile_create_lead`;
- `nexstep_mobile_add_comment`;
- `nexstep_mobile_complete_action`;
- `nexstep_mobile_transfer_action`;
- `nexstep_mobile_review_password_reset`.

Il révoque leur exécution pour `PUBLIC`, `anon` et `authenticated`, puis
l’accorde uniquement à `service_role`. Il ne contient aucun `DROP TABLE`,
`TRUNCATE` ou `DELETE`.

## 2. Installer le Supabase CLI

Sous Windows, la méthode globale officielle utilise Scoop :

```powershell
scoop bucket add supabase https://github.com/supabase/scoop-bucket.git
scoop install supabase
supabase --version
```

Alternative avec Node.js 20 ou plus récent :

```powershell
cd C:\chemin\vers\NexStep\mobile_app\supabase
npm install supabase --save-dev
npx supabase --version
```

Dans la suite, remplacer `supabase` par `npx supabase` si cette seconde méthode
a été choisie.

## 3. Lier le projet

Depuis `NexStep\mobile_app` :

```powershell
$env:NODE_OPTIONS = "--use-system-ca"
npx --yes supabase@latest login
```

`PROJECT_REF` est l’identifiant visible dans l’URL du Dashboard. Pour le projet
NexStep actuel, il s’agit de `smfpnijhmdajaezvxdit` :

```text
https://supabase.com/dashboard/project/PROJECT_REF
```

La connexion utilise le compte Supabase et ouvre le navigateur pour
l’autorisation. Elle ne demande pas `DATABASE_URL`.

## 4. Enregistrer le pepper côté serveur

La valeur doit être **strictement identique** au `APP_PIN_PEPPER` déjà utilisé
par Streamlit Cloud. Une valeur différente rendrait les PIN existants
inutilisables dans le mobile.

Méthode recommandée, sans placer la valeur dans l’historique PowerShell :

```powershell
$securePepper = Read-Host "APP_PIN_PEPPER existant" -AsSecureString
$env:APP_PIN_PEPPER = [System.Net.NetworkCredential]::new(
  "",
  $securePepper
).Password
supabase secrets set APP_PIN_PEPPER="$env:APP_PIN_PEPPER"
Remove-Item Env:APP_PIN_PEPPER
```

On peut aussi l’ajouter dans **Edge Functions > Secrets** dans le Dashboard.
Ne pas inventer une nouvelle valeur si l’application Streamlit utilise déjà
l’ancienne.

Supabase fournit automatiquement à l’Edge Function `SUPABASE_URL`,
`SUPABASE_PUBLISHABLE_KEYS` et `SUPABASE_SECRET_KEYS`. Il ne faut pas les
recopier dans le code.

## 5. Déployer l’Edge Function

Toujours depuis `NexStep\mobile_app` :

```powershell
npx --yes supabase@latest functions deploy nexstep-mobile-api `
  --project-ref smfpnijhmdajaezvxdit `
  --no-verify-jwt `
  --use-api `
  --workdir .
```

Le fichier `config.toml` désactive le contrôle JWT historique pour cette
fonction. Ce n’est pas un accès anonyme aux données : le code vérifie d’abord
la clé Publishable, puis les PIN/mot de passe ou le jeton de session NexStep.

### Déploiement guidé recommandé

Le script suivant regroupe l’authentification, la saisie masquée du pepper, le
déploiement et le test de santé. Il s’arrête tant que l’exécution du SQL additif
n’a pas été confirmée :

```powershell
cd C:\Users\tankamch\Dropbox\Business\scale.ag\Toward_NexStep\NexStep\mobile_app
powershell -ExecutionPolicy Bypass -File .\scripts\deploy_mobile_backend.ps1
```

Il faut lui fournir le `APP_PIN_PEPPER` **existant** de Streamlit Cloud et la
clé publique Publishable déjà saisie dans l’APK. Aucun de ces contenus n’est
écrit dans un fichier local.

## 6. Tester avant de compiler

Dans **Project Settings > API Keys**, copier la clé Publishable, puis :

```powershell
$projectUrl = "https://PROJECT_REF.supabase.co"
$publishableKey = Read-Host "Clé sb_publishable_..."

$headers = @{
  apikey = $publishableKey
  "Content-Type" = "application/json"
}
$body = @{
  operation = "health"
  payload = @{}
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "$projectUrl/functions/v1/nexstep-mobile-api" `
  -Headers $headers `
  -Body $body
```

Réponse attendue :

```text
ok   data
--   ----
True @{status=ok}
```

Une erreur `invalid_client_key` signifie que la clé n’est pas la clé
Publishable du même projet. Une erreur avant cette réponse invite à regarder
**Edge Functions > nexstep-mobile-api > Logs**.

## 7. Compiler l’APK

Pour un APK Debug configurable directement sur le téléphone :

```powershell
cd C:\chemin\vers\NexStep\mobile_app
powershell -ExecutionPolicy Bypass -File .\scripts\build_android.ps1 `
  -Configuration Debug `
  -CompileSdk 34 `
  -TargetSdk 34
```

Pour un APK déjà configuré, qui ouvre directement la connexion NexStep :

```powershell
cd C:\chemin\vers\NexStep\mobile_app
$env:NEXSTEP_SUPABASE_URL = "https://PROJECT_REF.supabase.co"
$env:NEXSTEP_SUPABASE_PUBLISHABLE_KEY = "sb_publishable_VOTRE_CLE"

powershell -ExecutionPolicy Bypass -File .\scripts\build_android.ps1 `
  -Configuration Debug `
  -SupabaseUrl $env:NEXSTEP_SUPABASE_URL `
  -PublishableKey $env:NEXSTEP_SUPABASE_PUBLISHABLE_KEY
```

`DATABASE_URL` n’intervient dans aucune étape de compilation.

## Références officielles

- https://supabase.com/docs/guides/functions
- https://supabase.com/docs/guides/functions/deploy
- https://supabase.com/docs/guides/functions/secrets
- https://supabase.com/docs/guides/functions/auth
- https://supabase.com/docs/guides/local-development/cli/getting-started
