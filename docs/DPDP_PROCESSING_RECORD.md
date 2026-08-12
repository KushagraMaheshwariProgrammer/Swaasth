# DPDP processing record

Evidence base for the Privacy Policy and store data-safety form. **Not legal advice.**

**Data fiduciary:** Kushagra Maheshwari, sole proprietor, Hyderabad, Telangana, India.  
**Contact:** app.swaasth@gmail.com (grievance officer and support).  
**Lawful basis (primary):** consent (Terms + Privacy clickwrap; medical-history consent; take-action consent; parental consent for minor profiles).  
**Last reviewed:** 12 August 2026.

## Processing activities

| # | Purpose | Data categories | Principals | Processor / location | Retention | Consent / notice |
|---|---------|-----------------|------------|----------------------|-----------|------------------|
| 1 | Account creation and sign-in | Email, Auth UID, sign-in method, adult attestation | Adult users | Google Firebase Auth — project `swaasth-5bf90` | Until account deletion | Terms/Privacy acceptance; 18+ checkbox at signup |
| 2 | Patient profiles | Name, birth year, gender, city/state, optional clinical history, parental consent | User-managed patients (may be minors) | Firestore `asia-south1` (Mumbai) + AES-GCM local cache | Until patient or account deletion | Parental consent required if birth year implies age < 18 |
| 3 | Bill / document analysis | Uploaded PDFs/images (transient), extracted line items, flags, reports | User / patient | Backend on Azure Container Apps **South India**; Azure OpenAI (pin to an Indian region — see [legal/azure-abuse-monitoring.md](legal/azure-abuse-monitoring.md)) | Files not retained after processing; structured reports only if medical-history consent is on | Privacy Policy §4, §7; medical-history consent for save |
| 4 | Saved reports and history | Analysis JSON (no raw OCR) | User | Firestore `users/{uid}/bills` + local encrypted mirror | Until revoke of medical-history consent, item delete, or account delete | Medical-history consent + per-patient `savePastBills` |
| 5 | Take-action / dispute drafts | Flags, complaint templates, escalation text | User | Generated on backend; consent timestamp on `users/{uid}` | Session + Firestore consent record | Take-action consent (`ACTION_CONSENT_VERSION`) |
| 6 | Support and grievances | Email content | User | Gmail (`app.swaasth@gmail.com`) | As needed to resolve + legal retention | Privacy Policy §16 |
| 7 | Guideline RAG (not personal data) | STG PDFs and embeddings | n/a | Private Azure Blob South India + in-image Chroma indexes | Until corpus refresh | n/a |

## Cross-border transfers

- Firestore: Mumbai (`asia-south1`).
- API: Azure Container Apps South India (`*.southindia.azurecontainerapps.io`).
- Azure OpenAI: region is implied by `AZURE_OPENAI_ENDPOINT`. **Confirm and pin to India (or an approved region) and disclose in the Privacy Policy.** Google and Microsoft may still operate support/abuse-monitoring outside India unless contractual exemptions apply.

## Rights handling

| Right | Channel |
|-------|---------|
| Access | Account settings → Download my data; or email app.swaasth@gmail.com |
| Correction | In-app patient/profile edits; or email |
| Erasure | `/account/delete` and `/delete-account`; medical-history revoke |
| Withdrawal of consent | Medical-history page; stop using the service |
| Grievance | app.swaasth@gmail.com — one month |
| Nomination | Email app.swaasth@gmail.com (Privacy Policy §11) |

## Significant Data Fiduciary

Health data at scale *may* trigger SDF duties (resident DPO, audits, DPIAs). Current status: **self-assessment — likely not SDF at present user volume; re-evaluate before scaling.** See [legal/significant-data-fiduciary.md](legal/significant-data-fiduciary.md).
