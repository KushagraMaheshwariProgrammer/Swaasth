export function canSaveMedicalHistory(accountConsent, patient) {
  return Boolean(accountConsent?.accepted) && patient?.savePastBills === true;
}

export function canViewMedicalHistory(accountConsent) {
  return Boolean(accountConsent?.accepted);
}

export function patientAllowsHistory(patient) {
  return patient?.savePastBills === true;
}
