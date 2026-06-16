import { TERMS_VERSION } from "../data/termsAndConditions.js";

const STORAGE_KEY = "swaasth_terms_acceptance_v1";

function readStore() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { users: {} };
    }
    const parsed = JSON.parse(raw);
    return parsed?.users ? parsed : { users: {} };
  } catch {
    return { users: {} };
  }
}

function writeStore(store) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
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
