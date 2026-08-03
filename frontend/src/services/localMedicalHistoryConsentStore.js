import { MEDICAL_HISTORY_CONSENT_VERSION } from "../data/medicalHistoryConsent";
import { getSecureJson, setSecureJson } from "./secureLocalStore";

const STORAGE_KEY = "swaasth_medical_history_consent_v1";

function readStore() {
  const parsed = getSecureJson(STORAGE_KEY, { users: {} });
  return parsed?.users ? parsed : { users: {} };
}

function writeStore(store) {
  setSecureJson(STORAGE_KEY, store);
}

export function getLocalMedicalHistoryConsent(userId) {
  const record = readStore().users[userId];
  if (!record) {
    return { accepted: false, declined: false, version: null };
  }
  if (record.declinedAt && !record.acceptedAt) {
    return { accepted: false, declined: true, version: record.consentVersion ?? null };
  }
  if (
    record.acceptedAt &&
    record.consentVersion === MEDICAL_HISTORY_CONSENT_VERSION
  ) {
    return { accepted: true, declined: false, version: MEDICAL_HISTORY_CONSENT_VERSION };
  }
  return { accepted: false, declined: false, version: record.consentVersion ?? null };
}

export function setLocalMedicalHistoryConsentAccepted(userId) {
  const store = readStore();
  store.users[userId] = {
    acceptedAt: new Date().toISOString(),
    consentVersion: MEDICAL_HISTORY_CONSENT_VERSION,
  };
  writeStore(store);
}

export function setLocalMedicalHistoryConsentDeclined(userId) {
  const store = readStore();
  store.users[userId] = {
    declinedAt: new Date().toISOString(),
    consentVersion: MEDICAL_HISTORY_CONSENT_VERSION,
  };
  writeStore(store);
}

export function clearLocalMedicalHistoryConsent(userId) {
  const store = readStore();
  delete store.users[userId];
  writeStore(store);
}
