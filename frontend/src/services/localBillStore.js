const STORAGE_KEY = "swaasth_local_bills_v1";

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

export function persistLocalBill(userId, billData) {
  const store = readStore();
  const entries = userEntries(store, userId);
  const localId =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `local-${Date.now()}-${Math.random().toString(36).slice(2)}`;

  entries.push({
    localId,
    billData,
    comparedAt: new Date().toISOString(),
    synced: false,
    firestoreId: null,
  });
  writeStore(store);
  return localId;
}

export function getLocalBills(userId) {
  const store = readStore();
  return store.users[userId] || [];
}

export function getUnsyncedLocalBills(userId) {
  return getLocalBills(userId).filter((entry) => !entry.synced);
}

export function getLocalBillById(userId, billId) {
  const match = getLocalBills(userId).find(
    (entry) => entry.localId === billId || entry.firestoreId === billId
  );
  return match ? localBillToHistoryEntry(match) : null;
}

export function markLocalBillSynced(userId, localId, firestoreId) {
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

export function updateLocalBillData(userId, billId, patch) {
  if (!userId || !billId || !patch || typeof patch !== "object") {
    return false;
  }
  const store = readStore();
  const entries = store.users[userId] || [];
  const entry = entries.find(
    (item) => item.localId === billId || item.firestoreId === billId
  );
  if (!entry) {
    return false;
  }
  entry.billData = {
    ...entry.billData,
    ...patch,
  };
  writeStore(store);
  return true;
}

export function localBillToHistoryEntry(entry) {
  return {
    id: entry.firestoreId || entry.localId,
    localOnly: !entry.firestoreId,
    ...entry.billData,
    comparedAt: entry.comparedAt,
    createdAt: entry.comparedAt,
  };
}

function billMatchesPatientIds(billData, idSet) {
  const data = billData || {};
  return idSet.has(data.patientId) || idSet.has(data.patient?.id);
}

export function removeLocalBill(userId, billId) {
  if (!userId || !billId) {
    return false;
  }
  const store = readStore();
  const entries = store.users[userId] || [];
  const remaining = entries.filter(
    (entry) => entry.localId !== billId && entry.firestoreId !== billId
  );
  if (remaining.length === entries.length) {
    return false;
  }
  store.users[userId] = remaining;
  writeStore(store);
  return true;
}

export function removeLocalBillsForPatientIds(userId, patientIds) {
  if (!userId || !patientIds?.length) {
    return 0;
  }
  const idSet = new Set(patientIds.filter(Boolean));
  const store = readStore();
  const entries = store.users[userId] || [];
  const remaining = entries.filter((entry) => !billMatchesPatientIds(entry.billData, idSet));
  const removed = entries.length - remaining.length;
  if (removed > 0) {
    store.users[userId] = remaining;
    writeStore(store);
  }
  return removed;
}
