import { isMinorBirthYear } from "./patientAge";
import {
  GUARDIAN_RELATIONSHIP_OPTIONS,
  PARENTAL_CONSENT_VERSION,
} from "../data/parentalConsent";

const RELATIONSHIP_IDS = new Set(
  GUARDIAN_RELATIONSHIP_OPTIONS.map((option) => option.id)
);

/**
 * Returns a sanitized parental-consent record, or null when the value is
 * missing or malformed. The record is the DPDP audit trail stored on the
 * patient document.
 */
export function normalizeParentalConsent(value) {
  if (!value || typeof value !== "object") {
    return null;
  }
  const guardianName = typeof value.guardianName === "string" ? value.guardianName.trim() : "";
  const relationship = typeof value.relationship === "string" ? value.relationship : "";
  const guardianUid = typeof value.guardianUid === "string" ? value.guardianUid : "";
  const guardianEmail = typeof value.guardianEmail === "string" ? value.guardianEmail : "";
  const consentVersion = typeof value.consentVersion === "string" ? value.consentVersion : "";
  const consentedAt = typeof value.consentedAt === "string" ? value.consentedAt : "";
  const verificationMethod =
    typeof value.verificationMethod === "string" ? value.verificationMethod : "";

  if (
    !guardianName ||
    !RELATIONSHIP_IDS.has(relationship) ||
    !guardianUid ||
    !consentVersion ||
    !consentedAt ||
    !verificationMethod
  ) {
    return null;
  }

  return {
    guardianName: guardianName.slice(0, 200),
    relationship,
    guardianUid,
    guardianEmail,
    consentVersion,
    consentedAt,
    verificationMethod,
  };
}

export function buildParentalConsentRecord({
  guardianName,
  relationship,
  guardianUid,
  guardianEmail,
  verificationMethod,
}) {
  return normalizeParentalConsent({
    guardianName,
    relationship,
    guardianUid,
    guardianEmail: guardianEmail || "",
    consentVersion: PARENTAL_CONSENT_VERSION,
    consentedAt: new Date().toISOString(),
    verificationMethod,
  });
}

export function requiresParentalConsent(birthYear) {
  return isMinorBirthYear(birthYear);
}

export function hasParentalConsent(patientData) {
  return normalizeParentalConsent(patientData?.parentalConsent) != null;
}
