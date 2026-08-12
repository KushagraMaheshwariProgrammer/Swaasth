# CDSCO classification memo — treatment-audit feature

**Status:** Draft for Indian health-tech counsel. Not a filing and not legal advice.  
**Date:** 12 August 2026  
**Product:** Swaasth (operator: Kushagra Maheshwari, sole proprietor, Hyderabad)

## Question

Does the AI treatment-audit / guideline-comparison feature constitute a medical device (including Software as a Medical Device) under the Medical Device Rules, 2017 and the February 2020 notification bringing all devices under the Drugs & Cosmetics Act?

## Intended use (as shipped)

Swaasth compares user-uploaded bills, prescriptions, and clinical documents with published ICMR / CEA STG / CRC guideline excerpts and NPPA price lists. Outputs are framed as **questions to discuss with the treating doctor** and **billing-documentation clarifications**. The product states it does not diagnose, treat, prescribe, or decide medical necessity.

Code anchors: `backend/app/services/treatment_audit.py` (`_TRIANGLE_AUDIT_SYSTEM`), Terms §2, in-report `CLINICAL_SECTION_DISCLAIMER`.

## Facts counsel should weigh

1. Software that is *intended* to support diagnosis, treatment, or mitigation of disease can be regulated even if labelled “informational.”
2. Flag types still include identifiers such as `DIAGNOSIS_UNSUPPORTED` and `NOT_INDICATED_MEDICINE` (internal enums). Display labels and reasons have been rewritten as questions; residual risk remains if marketing or UI implies clinical judgement.
3. `clinical_alignment.documents_consistent` is a tri-state clarification label, not a diagnosis.
4. There is no clinician-in-the-loop before the patient sees the output.
5. Landing copy has been limited to bill review + “questions to discuss with your doctor.”

## Interim engineering position (until an opinion is obtained)

- Do not market “check whether treatment was appropriate,” “second opinion,” or “clinical decision support.”
- Keep the guardrail pass and “discuss with your doctor” suffix mandatory.
- Do not tell users to start, stop, or switch medicines.

## Ask of counsel

1. Classification (not a device / Class A–C SaMD / other).
2. If a device: CDSCO registration path, labelling, and QMS.
3. Whether billing-only mode (NPPA / duplicates, no STG comparison) would change the answer.
4. Advertising and Drugs & Magic Remedies implications, if any.
