import { ACTION_CONSENT_VERSION } from "../data/actionConsent";
import { acceptActionConsent } from "./userProfile";

const STORAGE_KEY = "swaasth_action_consent_v1";

export function hasActionConsent() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return false;
    }
    if (raw === "true") {
      return true;
    }
    const parsed = JSON.parse(raw);
    return Boolean(parsed?.accepted) && parsed?.version === ACTION_CONSENT_VERSION;
  } catch {
    return false;
  }
}

export function setActionConsentAccepted() {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      accepted: true,
      version: ACTION_CONSENT_VERSION,
      acceptedAt: new Date().toISOString(),
    }));
  } catch {
    // Session storage unavailable — consent not persisted for this session.
  }
}

export async function recordActionConsent(userId) {
  setActionConsentAccepted();
  if (userId) {
    await acceptActionConsent(userId);
  }
}
