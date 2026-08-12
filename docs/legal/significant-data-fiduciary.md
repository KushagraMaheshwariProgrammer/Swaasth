# Significant Data Fiduciary — self-assessment

**Date:** 12 August 2026  
**Fiduciary:** Kushagra Maheshwari, sole proprietor (Swaasth)  
**Not a legal determination.** Re-do when user volume, data categories, or DPDP Rules notifications change.

## DPDP Act s.10 (indicative factors)

The Central Government may notify a Significant Data Fiduciary based on volume, sensitivity, risk to electoral democracy / security / public order, and other factors. Health data is highly sensitive.

| Factor | Current position | SDF-leaning? |
|--------|------------------|--------------|
| Volume of personal data | Early-stage consumer app; not a national-scale processor | No, until growth |
| Sensitivity | Health / SPDI-class data (bills, prescriptions, diagnoses) | Yes |
| Risk of harm | Mis-analysis could affect billing disputes; clinical flags are question-framed | Moderate |
| Use of new tech (AI) | Azure OpenAI on health documents | Yes |
| Children’s data | Minor *patient profiles* with parental consent; accounts are 18+ | Partial |
| Cross-border | Firestore Mumbai; API South India; OpenAI region to be pinned | Depends on OpenAI region |

## Conclusion (today)

**Treat as not notified SDF** until a government notification or a material increase in scale. Do **not** skip: privacy notice, consent records, grievance officer, breach runbook, deletion, and processor contracts.

If notified or if monthly active users / stored health records grow into the “large fiduciary” range counsel identifies:

1. Appoint a resident Data Protection Officer.
2. Appoint an independent data auditor.
3. Conduct Data Protection Impact Assessments (DPIA) for the treatment-audit and Azure OpenAI processing.
4. Periodic audits as prescribed.

**Next review:** when crossing a user-volume threshold agreed with counsel, or on any SDF notification in the Gazette.
