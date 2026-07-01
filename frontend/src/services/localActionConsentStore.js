const STORAGE_KEY = "swaasth_action_consent_v1";

export function hasActionConsent() {
  try {
    return sessionStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export function setActionConsentAccepted() {
  try {
    sessionStorage.setItem(STORAGE_KEY, "true");
  } catch {
    // Session storage unavailable — consent not persisted for this session.
  }
}
