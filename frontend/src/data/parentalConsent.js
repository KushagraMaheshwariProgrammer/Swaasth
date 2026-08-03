export const PARENTAL_CONSENT_VERSION = "2026-08-03";
export const PARENTAL_CONSENT_LAST_UPDATED = "3 August 2026";

export const GUARDIAN_RELATIONSHIP_OPTIONS = [
  { id: "mother", label: "Mother" },
  { id: "father", label: "Father" },
  { id: "legal_guardian", label: "Legal guardian" },
];

export function guardianRelationshipLabel(relationship) {
  return (
    GUARDIAN_RELATIONSHIP_OPTIONS.find((option) => option.id === relationship)
      ?.label || relationship || "—"
  );
}

export const PARENTAL_CONSENT_SECTIONS = [
  {
    title: "Why we need parental consent",
    paragraphs: [
      "The patient profile you are creating is for a person below 18 years of age. Under India's Digital Personal Data Protection Act, 2023 (DPDP Act), Swaasth must obtain verifiable consent from the child's parent or lawful guardian before processing the child's personal data.",
      "Only a parent or lawful guardian of this child may give this consent. By continuing, you declare that you are that parent or lawful guardian.",
    ],
    bullets: [],
  },
  {
    title: "What data will be processed",
    paragraphs: [
      "The child's profile details you enter — name, birth year, gender, and location — are stored in your Swaasth account and used to check medical bills, prescriptions, and clinical documents for this child.",
      "If you also opt in to saving medical history, structured analysis reports for this child's documents are saved to your account. Swaasth does not store original uploaded files or raw scanned text.",
    ],
    bullets: [],
  },
  {
    title: "What Swaasth will never do with a child's data",
    paragraphs: [],
    bullets: [
      "No tracking or behavioural monitoring of the child.",
      "No targeted advertising directed at the child.",
      "No processing that is detrimental to the well-being of the child.",
      "No sharing of the child's data with third parties for marketing.",
    ],
  },
  {
    title: "How your consent is verified",
    paragraphs: [
      "Consent is given from your verified Swaasth account. To make this consent verifiable, you must confirm your identity now by re-entering your password (or re-confirming with Google).",
      "Swaasth records your name, your relationship to the child, your account email, the consent version, the time of consent, and the verification method used. This record is kept with the child's profile as proof of consent.",
    ],
    bullets: [],
  },
  {
    title: "Your rights as parent or guardian",
    paragraphs: [
      "You may withdraw this consent at any time by deleting the child's patient profile, which permanently removes the child's profile and all linked reports from your account and this device.",
      "You may review the recorded consent details on the child's patient page at any time.",
    ],
    bullets: [],
  },
];

export function parentalConsentDeclaration(childName) {
  const name = childName?.trim() || "this child";
  return (
    `I declare that I am the parent or lawful guardian of ${name}, ` +
    "and I give my consent to Swaasth processing this child's personal data as described above."
  );
}
