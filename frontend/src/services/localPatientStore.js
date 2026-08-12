import { normalizeClinicalHistory } from "../utils/clinicalHistory";
import { normalizeParentalConsent } from "../utils/parentalConsent";
import { getSecureJson, setSecureJson } from "./secureLocalStore";

const STORAGE_KEY = "swaasth_local_patients_v1";

function readStore() {
  const parsed = getSecureJson(STORAGE_KEY, { users: {} });
  return parsed?.users ? parsed : { users: {} };
}

function writeStore(store) {
  setSecureJson(STORAGE_KEY, store);
}

function userEntries(store, userId) {
  if (!store.users[userId]) {
    store.users[userId] = [];
  }
  return store.users[userId];
}

export function persistLocalPatient(userId, patientData, localId = null) {
  if (!userId) {
    throw new Error("Missing user id for patient storage.");
  }
  const store = readStore();
  const entries = userEntries(store, userId);
  const id =
    localId ||
    (typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `local-${Date.now()}-${Math.random().toString(36).slice(2)}`);

  const existing = entries.find((entry) => entry.localId === id);
  const record = {
    localId: id,
    patientData: {
      name: patientData.name?.trim() || "",
      birthYear: Number(patientData.birthYear) || null,
      gender: patientData.gender || "",
      state: patientData.state?.trim() || "",
      city: patientData.city?.trim() || "",
      savePastBills: patientData?.savePastBills === true,
      clinicalHistory: normalizeClinicalHistory(patientData?.clinicalHistory),
      parentalConsent: normalizeParentalConsent(patientData?.parentalConsent),
    },
    firestoreId: existing?.firestoreId || null,
    synced: false,
    updatedAt: Date.now(),
  };

  const index = entries.findIndex((entry) => entry.localId === id);
  if (index >= 0) {
    entries[index] = record;
  } else {
    entries.push(record);
  }

  writeStore(store);
  return id;
}

export function markLocalPatientSynced(userId, localId, firestoreId) {
  const store = readStore();
  const entries = userEntries(store, userId);
  const entry = entries.find((item) => item.localId === localId);
  if (entry) {
    entry.firestoreId = firestoreId;
    entry.synced = true;
    writeStore(store);
  }
}

export function getLocalPatients(userId) {
  if (!userId) {
    return [];
  }
  return readStore().users[userId] || [];
}

export function getUnsyncedLocalPatients(userId) {
  return getLocalPatients(userId).filter((entry) => !entry.synced);
}

export function localPatientToEntry(entry) {
  return {
    id: entry.firestoreId || entry.localId,
    localId: entry.localId,
    firestoreId: entry.firestoreId || null,
    localOnly: !entry.firestoreId,
    ...entry.patientData,
  };
}

export function getLocalPatientById(userId, patientId) {
  const match = getLocalPatients(userId).find(
    (entry) =>
      entry.localId === patientId || entry.firestoreId === patientId
  );
  return match ? localPatientToEntry(match) : null;
}

export function removeLocalPatient(userId, patientId) {
  const store = readStore();
  const entries = userEntries(store, userId);
  store.users[userId] = entries.filter(
    (entry) => entry.localId !== patientId && entry.firestoreId !== patientId
  );
  writeStore(store);
}

export function clearLocalPatientsForUser(userId) {
  if (!userId) {
    return;
  }
  const store = readStore();
  if (store.users[userId]) {
    delete store.users[userId];
    writeStore(store);
  }
}
