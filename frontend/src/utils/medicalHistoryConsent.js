import { getLocalMedicalHistoryConsent } from "../services/localMedicalHistoryConsentStore";

export function resolveAccountConsent(
  userId,
  remoteAccepted,
  { loading = false } = {}
) {
  if (remoteAccepted === true) {
    return { accepted: true };
  }
  if (loading || remoteAccepted == null) {
    return getLocalMedicalHistoryConsent(userId);
  }
  return { accepted: false };
}

export function canSaveMedicalHistory(accountConsent, patient) {
  return Boolean(accountConsent?.accepted) && patient?.savePastBills !== false;
}

export function canViewMedicalHistory(accountConsent) {
  return Boolean(accountConsent?.accepted);
}

export function patientAllowsHistory(patient) {
  return patient?.savePastBills !== false;
}
