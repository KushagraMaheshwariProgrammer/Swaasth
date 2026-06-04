const STORAGE_KEY = "swaasth_local_patients_v1";

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
      age: Number(patientData.age) || 0,
      gender: patientData.gender || "",
      ayushmanEligible: Boolean(patientData.ayushmanEligible),
    },
    synced: existing?.synced ?? false,
    firestoreId: existing?.firestoreId ?? null,
    updatedAt: new Date().toISOString(),
  };

  if (existing) {
    Object.assign(existing, record);
  } else {
    entries.push(record);
  }
  writeStore(store);
  return id;
}

export function getLocalPatients(userId) {
  const store = readStore();
  return store.users[userId] || [];
}

export function getUnsyncedLocalPatients(userId) {
  return getLocalPatients(userId).filter((entry) => !entry.synced);
}

export function markLocalPatientSynced(userId, localId, firestoreId) {
  const store = readStore();
  const entries = store.users[userId] || [];
  const entry = entries.find((item) => item.localId === localId);
  if (!entry) {
    return;
  }
  entry.synced = true;
  entry.firestoreId = firestoreId;
  writeStore(store);
}

export function localPatientToEntry(entry) {
  return {
    id: entry.firestoreId || entry.localId,
    localId: entry.localId,
    firestoreId: entry.firestoreId || null,
    localOnly: !entry.firestoreId,
    ...entry.patientData,
    updatedAt: entry.updatedAt,
  };
}

export function getLocalPatientById(userId, patientId) {
  const match = getLocalPatients(userId).find(
    (entry) => entry.localId === patientId || entry.firestoreId === patientId
  );
  return match ? localPatientToEntry(match) : null;
}

export function removeLocalPatient(userId, patientId) {
  const store = readStore();
  const entries = store.users[userId] || [];
  store.users[userId] = entries.filter(
    (entry) =>
      entry.localId !== patientId && entry.firestoreId !== patientId
  );
  writeStore(store);
}
