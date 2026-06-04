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

export function getUnsyncedLocalBills(userId) {
  const store = readStore();
  return (store.users[userId] || []).filter((entry) => !entry.synced);
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

export function localBillToHistoryEntry(entry) {
  return {
    id: entry.firestoreId || entry.localId,
    localOnly: !entry.firestoreId,
    ...entry.billData,
    comparedAt: entry.comparedAt,
    createdAt: entry.comparedAt,
  };
}
