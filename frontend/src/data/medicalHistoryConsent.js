export const MEDICAL_HISTORY_CONSENT_VERSION = "2026-08-03";
export const MEDICAL_HISTORY_CONSENT_LAST_UPDATED = "3 August 2026";

export const MEDICAL_HISTORY_CONSENT_SECTIONS = [
  {
    title: "What medical history means in Swaasth",
    paragraphs: [
      "Medical history in Swaasth refers to saved analysis reports from your document checks — including line-item bill reviews, prescription audits, and clinical context you provide.",
      "Swaasth does not store your original uploaded files or raw OCR text. Only structured analysis results and metadata (such as filenames and report summaries) are saved to your account when you opt in.",
    ],
    bullets: [],
  },
  {
    title: "Where your history is stored",
    paragraphs: [
      "Saved reports are stored in your Swaasth account under your user profile and linked to the patient profile you selected during the check.",
      "Only you can access your saved history while signed in to your account. Device copies are encrypted at rest on this device.",
    ],
    bullets: [],
  },
  {
    title: "Your choices",
    paragraphs: [
      "Saving medical history is entirely optional. You can use Swaasth to analyze documents without saving any history.",
      "You must grant account-level consent to enable the history feature. For each patient, you must also opt in when creating or editing their profile.",
      "You can review or change your account consent at any time from Account settings or the Medical history consent page.",
    ],
    bullets: [],
  },
  {
    title: "Deleting your data",
    paragraphs: [
      "You can delete individual saved reports from the Past bills page at any time.",
      "If you revoke consent, all previously saved reports and medical documents are permanently deleted from your account and this device, and new reports will not be saved.",
      "Deleting a patient profile will also remove reports linked to that patient.",
    ],
    bullets: [],
  },
];
