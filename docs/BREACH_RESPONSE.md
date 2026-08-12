# Personal-data breach response

Use this runbook if personal data (especially health data) is lost, stolen, exposed, or accessed without authorisation.

**Not legal advice.** Confirm notification duties with counsel against the DPDP Act 2023 and the DPDP Rules then in force.

## Contacts

| Role | Who | Channel |
|------|-----|---------|
| Data fiduciary / grievance officer / support | Kushagra Maheshwari | app.swaasth@gmail.com |
| Firebase | Google Cloud / Firebase console | project `swaasth-5bf90` |
| API / OpenAI | Azure portal | Container App `swaasth-api`, OpenAI resource |

## 1. Detect

Triggers: user report, Firebase/Auth alert, Azure diagnostic, GitHub secret scan, unusual API traffic, lost device with an unlocked session.

Record: time detected, how detected, systems involved, whether health data is in scope.

## 2. Contain

- Rotate exposed keys (Azure OpenAI, SAS URLs, Firebase if applicable). See [SECRETS.md](SECRETS.md).
- Disable compromised accounts; force sign-out if possible.
- Take the API offline only if leakage is ongoing (`ENV=production` Container App).
- Do **not** destroy logs needed for the assessment.

## 3. Assess

Answer, in writing:

1. What data categories were involved (account, patient, reports, documents, prompts)?
2. How many principals are affected (known UIDs / emails)?
3. Is the data encrypted and were keys exposed?
4. Likelihood of identity theft, discrimination, or medical confidentiality harm?
5. Is this a personal-data breach that must be reported to the Data Protection Board and to affected principals under the DPDP Act / Rules then in force?

## 4. Notify

- **Data Protection Board of India** — follow the form and timeline in the DPDP Rules then in force (treat as urgent; do not wait for a perfect forensic report).
- **Affected users** — email from app.swaasth@gmail.com: what happened, what data, what we are doing, what they should do (password reset, watch hospital/insurer mail), grievance contact.
- **Processors** — notify Google / Microsoft if their services were the source or must assist.

Keep copies of every notice.

## 5. Recover and learn

- Restore from known-good backups only if integrity is verified (`scripts/restore_firestore_from_backup.py` is for planned migrations, not blind incident restore).
- Patch the root cause.
- Update [SECURITY.md](SECURITY.md) and this runbook with the date and a short after-action note (no unnecessary personal data in git).

## 6. Tabletop (annual)

Walk through a lost-laptop scenario and an Azure-key-leak scenario once a year. Note the date here:

| Date | Scenario | Notes |
|------|----------|-------|
|  |  |  |
