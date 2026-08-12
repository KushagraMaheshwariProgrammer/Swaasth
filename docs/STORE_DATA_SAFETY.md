# Play / Galaxy Store — Data Safety answers (draft)

Complete the store form **after** the privacy policy URL and account-deletion URL are live. Source: [DPDP_PROCESSING_RECORD.md](../DPDP_PROCESSING_RECORD.md).

## URLs

| Field | Value |
|-------|--------|
| Privacy policy | https://swaasth.in/privacy |
| Account deletion (web) | https://swaasth.in/delete-account |
| In-app deletion | Account settings → Delete account (`/account/delete`) |
| Open source | https://swaasth.in/source |
| Licenses | https://swaasth.in/licenses |

## Data collected (declare)

| Category | Collected? | Shared? | Purpose | Optional? |
|----------|------------|---------|---------|-----------|
| Email | Yes (Auth) | With Google (Firebase) | Account | No |
| Name | Yes (patient profiles the user enters) | With Google (Firestore); with Microsoft (Azure OpenAI) during analysis | App functionality | Yes (user-entered) |
| Health info | Yes (documents, history, reports) | Microsoft Azure OpenAI (transient analysis); Google Firestore (saved reports if consented) | App functionality | Analysis required for the feature; cloud save is optional |
| Photos / files | User-selected documents only (file picker, not camera roll scrape) | Microsoft (transient) | App functionality | Yes |
| Approximate location | City/state the user types — **not** GPS | Google Firestore | App functionality | Yes |

**Not collected:** GPS, contacts, camera/mic capture, advertising ID, web browsing.

## Sharing

- **Google:** Firebase Auth + Firestore (account and saved data).
- **Microsoft:** Azure OpenAI for OCR/analysis of uploaded document content. Not used for advertising. Not sold.

## Security

- Data encrypted in transit (TLS).
- Users can request deletion (in-app + web).
- Committed to Play Families / health-app policies: review Health Apps policy before the next submission.

## Health Apps policy notes

Swaasth handles personal health records the user uploads. Do not claim to be a medical device or to provide treatment. Keep the informational / “discuss with your doctor” framing in the store listing, matching Terms §2.
