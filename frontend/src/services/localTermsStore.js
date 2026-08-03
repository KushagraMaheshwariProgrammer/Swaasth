import { TERMS_VERSION } from "../data/termsAndConditions.js";
import { getSecureJson, setSecureJson } from "./secureLocalStore";

const STORAGE_KEY = "swaasth_terms_acceptance_v1";

function readStore() {
  const parsed = getSecureJson(STORAGE_KEY, { users: {} });
  return parsed?.users ? parsed : { users: {} };
}

function writeStore(store) {
  setSecureJson(STORAGE_KEY, store);
}

export function getLocalTermsAcceptance(userId) {
  const record = readStore().users[userId];
  if (!record?.acceptedAt || record.termsVersion !== TERMS_VERSION) {
    return { accepted: false, version: record?.termsVersion ?? null };
  }
  return { accepted: true, version: TERMS_VERSION };
}

export function setLocalTermsAcceptance(userId) {
  const store = readStore();
  store.users[userId] = {
    acceptedAt: new Date().toISOString(),
    termsVersion: TERMS_VERSION,
  };
  writeStore(store);
}

export function clearLocalTermsAcceptance(userId) {
  const store = readStore();
  delete store.users[userId];
  writeStore(store);
}
