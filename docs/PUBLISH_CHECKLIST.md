# Publish checklist — remaining operator tasks

Last updated: 12 August 2026.

Engineering and most infra for the legal remediation are done. Use this list to finish publishing.

## Done in this pass (you do not need to redo)

- [x] Contact email set to **app.swaasth@gmail.com** (Terms, Privacy, deletion page, docs)
- [x] Firestore rules deployed to `swaasth-5bf90` (action consent, adult attestation, `deletionRequests`)
- [x] Azure OpenAI confirmed in **southindia** (`swaasthbot`)
- [x] Guideline corpus purged from public git history (force-pushed)
- [x] Private blob created: storage account `swaasthguidelines` (South India), blob `guidelines/corpus.tar.gz`
- [x] SAS URL saved locally at `~/Desktop/swaasth/GUIDELINE_CORPUS_SAS_URL.txt` and as Container App secret `guideline-corpus-sas-url`
- [x] Frontend built and deployed to Firebase Hosting: https://swaasth-5bf90.web.app
- [x] Deploy script updated to pass corpus SAS as base64 build-arg (raw SAS breaks ACR)
- [x] API image rebuilt with private corpus and Container App updated (2026-08-12)
- [x] Legal remediation committed and pushed on `galaxy-store-code`
- [x] Store-facing policy URLs use Firebase Hosting `.web.app` (custom domain optional for an app-first launch)

## Store-facing URLs (use these)

Base: **https://swaasth-5bf90.web.app**

| Purpose | URL |
|---------|-----|
| Privacy policy (Play / Galaxy Data Safety) | https://swaasth-5bf90.web.app/privacy |
| Account deletion (store requirement) | https://swaasth-5bf90.web.app/delete-account |
| Terms | https://swaasth-5bf90.web.app/terms |
| Open-source / AGPL offer | https://swaasth-5bf90.web.app/source |
| Third-party licenses | https://swaasth-5bf90.web.app/licenses |
| In-app account deletion (signed-in) | https://swaasth-5bf90.web.app/account/delete |
| Landing | https://swaasth-5bf90.web.app/ |
| Login | https://swaasth-5bf90.web.app/login |

API (not for store listing forms):  
https://swaasth-api.redbay-ce8ac868.southindia.azurecontainerapps.io

## You still need to do

### 1. Azure OpenAI modified abuse-monitoring (strongly recommended; not a Play blocker)

Default Azure OpenAI may retain prompts ~30 days for human abuse review. Health bills/prescriptions in prompts make that uncomfortable under DPDP confidentiality expectations.

**You** must apply — it is not a portal toggle I can flip:

1. Open the Limited Access / Modified Abuse Monitoring form: https://aka.ms/oai/modifiedaccess (also linked from Microsoft’s [abuse monitoring docs](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/abuse-monitoring)).
2. Use subscription for resource `swaasthbot` (South India). Justification: Indian health-document analysis; do not want human review of patient prompts.
3. Eligibility is gated (often EA/MCA / managed customer). If Pay-As-You-Go and denied, document the attempt and keep redaction / minimal-prompt practices.
4. If approved, disable abuse monitoring on the content filter in Azure AI Foundry and verify.

Draft notes: `docs/legal/azure-abuse-monitoring.md`.

**Not required to submit the Android build**, but do it before heavy production health volume if you can.

### 2. Accept Microsoft + Google DPAs (you must click; agent cannot)

These are click-through agreements under **your** Azure / Google Cloud login. I cannot accept them for you.

- **Microsoft:** Azure Portal → search “Data Protection Addendum” / Privacy → accept Microsoft Products and Services DPA for the subscription that hosts OpenAI + Container Apps. Notes: `docs/legal/dpa-request-microsoft.md`
- **Google:** Google Cloud Console (project `swaasth-5bf90`) → Account / Legal / GDPR or Cloud Data Processing Addendum → accept for Firebase Auth, Firestore, Hosting. Notes: `docs/legal/dpa-request-google.md`

Download/PDF the accepted terms into your records folder.

### 3. Monitor app.swaasth@gmail.com (required)

Grievance officer + support + deletion requests. Check daily.

### 4. Android / store listing (required to publish)

1. Bump `versionCode` / `versionName` in `frontend/android/app/build.gradle` if needed (currently `1` / `1.0`).
2. Build a signed release AAB/APK in Android Studio.
3. Play Console (or Galaxy Store):
   - Privacy policy: https://swaasth-5bf90.web.app/privacy
   - Account deletion: https://swaasth-5bf90.web.app/delete-account
   - Data Safety: `docs/STORE_DATA_SAFETY.md`
   - Health Apps: no medical-device claims; informational framing only
4. Screenshots and description must match Terms §2 (not diagnosis/treatment).

### 5. Legal / business (not a store upload gate — risk reduction)

See the status report in chat / notes below. Counsel review, CDSCO, trademark, and IP assignments reduce founder/personal risk; they are not Play Console form fields.

### 6. Optional polish

- Custom domain `swaasth.in` — **optional** for an app-first launch; `.web.app` HTTPS URLs satisfy store policy URL requirements.
- Branded API host — optional.
- **Guideline SAS rotation** — **not required** unless the URL was committed, pasted into a public ticket, or leaked. Current SAS lives only outside the repo and in a Container App secret; do not rotate prophylactically (would force an API rebuild).
