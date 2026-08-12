# Security practices (SPDI Rule 8 / IT Act §43A)

This note describes the reasonable security practices Swaasth currently uses to protect sensitive personal data, including health-related information. It is the document we can point to after an incident. It is **not** an ISO 27001 certificate.

**Data fiduciary:** Kushagra Maheshwari, sole proprietor, Hyderabad, Telangana.  
**Grievance officer:** Kushagra Maheshwari — app.swaasth@gmail.com (one-month resolution target).

## Technical measures

| Control | How it is implemented |
|---------|------------------------|
| Encryption in transit | HTTPS/TLS for the website, API (`api.swaasth.in` / Azure Container Apps South India), and Firebase. |
| Encryption at rest (device) | AES-GCM 256-bit local cache (`frontend/src/services/secureLocalStore.js`); key in IndexedDB. |
| Encryption at rest (cloud) | Google Cloud / Firestore default encryption; Azure storage for the private guideline blob. |
| Authentication | Firebase Auth (email/password + Google). Analysis API routes require a Firebase ID token. |
| Access control | Firestore rules: owner-only `users/{uid}/…`. Raw OCR text is blocked from persistence. Minor patient profiles require a parental-consent record with `guardianUid == auth.uid`. |
| Data minimisation | Original upload files are not stored after processing. Raw OCR is not written to Firestore. |
| Secrets | Azure OpenAI keys and SAS URLs live in environment variables / Container Apps secrets, not in git. See [SECRETS.md](SECRETS.md). |
| Logging | Backend does not log prompt/response bodies from Azure OpenAI. |
| Account deletion | In-app `/account/delete` (reauth → wipe → Auth delete) plus public `/delete-account`. A `deletionRequests/{uid}` record is written first so partial failures are discoverable. |

## Organisational measures

- Access to production Firebase, Azure, and GitHub is limited to the operator.
- Guideline PDFs are not in the public repository.
- Consent records (terms, privacy, medical history, take-action, adult attestation) are versioned and timestamped on `users/{uid}`.
- A written [breach response](BREACH_RESPONSE.md) runbook exists.

## Residual risk

No system is completely secure. Azure OpenAI abuse monitoring may retain prompts unless a modified-abuse-monitoring exemption is approved (see `docs/legal/azure-abuse-monitoring.md`). Client-driven deletion can fail mid-flow; the deletion-request record is the compensating control until a server-side cleanup function is added.

## Review

Review this document when processors, regions, or data categories change, and at least annually.
