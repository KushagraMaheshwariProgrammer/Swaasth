import {
  addDoc,
  collection,
  doc,
  getDoc,
  getDocs,
  serverTimestamp,
} from "firebase/firestore";
import { db } from "../firebase";
import {
  getUnsyncedLocalBills,
  localBillToHistoryEntry,
  markLocalBillSynced,
  persistLocalBill,
} from "./localBillStore";

function billsCollection(userId) {
  return collection(db, "users", userId, "bills");
}

export function sanitizeForFirestore(value) {
  if (value === undefined) {
    return undefined;
  }
  if (value === null || typeof value !== "object") {
    return value;
  }
  if (Array.isArray(value)) {
    return value
      .map((item) => sanitizeForFirestore(item))
      .filter((item) => item !== undefined);
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  if (typeof value.toDate === "function") {
    return value;
  }

  const cleaned = {};
  for (const [key, nested] of Object.entries(value)) {
    const sanitized = sanitizeForFirestore(nested);
    if (sanitized !== undefined) {
      cleaned[key] = sanitized;
    }
  }
  return cleaned;
}

export function getBillSortTime(bill) {
  const timestamp = bill?.createdAt;
  if (timestamp?.toDate) {
    return timestamp.toDate().getTime();
  }
  if (timestamp?.seconds) {
    return timestamp.seconds * 1000;
  }
  if (typeof timestamp === "string" || typeof timestamp === "number") {
    const parsed = new Date(timestamp).getTime();
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  if (bill?.comparedAt) {
    const parsed = new Date(bill.comparedAt).getTime();
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  return 0;
}

function sortBillsNewestFirst(bills) {
  return [...bills].sort((a, b) => getBillSortTime(b) - getBillSortTime(a));
}

async function fetchCloudBills(userId) {
  const snapshot = await getDocs(billsCollection(userId));
  return snapshot.docs.map((entry) => ({
    id: entry.id,
    ...entry.data(),
  }));
}

export async function saveBill(userId, billData, options = {}) {
  const payload = sanitizeForFirestore({
    ...billData,
    comparedAt: billData.comparedAt || new Date().toISOString(),
    clientId: options.localId || billData.clientId || null,
    createdAt: serverTimestamp(),
  });

  const docRef = await addDoc(billsCollection(userId), payload);
  return docRef.id;
}

export async function syncPendingBills(userId) {
  const pending = getUnsyncedLocalBills(userId);
  let syncedCount = 0;

  for (const entry of pending) {
    try {
      const firestoreId = await saveBill(userId, entry.billData, {
        localId: entry.localId,
      });
      markLocalBillSynced(userId, entry.localId, firestoreId);
      syncedCount += 1;
    } catch (error) {
      console.error("Failed to sync local bill to Firebase:", error);
    }
  }

  return syncedCount;
}

export async function getUserBills(userId) {
  await syncPendingBills(userId);

  const cloudBills = await fetchCloudBills(userId);
  const cloudClientIds = new Set(
    cloudBills.map((bill) => bill.clientId).filter(Boolean)
  );

  const localOnly = getUnsyncedLocalBills(userId)
    .filter((entry) => !cloudClientIds.has(entry.localId))
    .map(localBillToHistoryEntry);

  return sortBillsNewestFirst([...cloudBills, ...localOnly]);
}

export async function getBill(userId, billId) {
  const billRef = doc(db, "users", userId, "bills", billId);
  const snapshot = await getDoc(billRef);
  if (snapshot.exists()) {
    return { id: snapshot.id, ...snapshot.data() };
  }

  const localMatch = getUnsyncedLocalBills(userId).find(
    (entry) => entry.localId === billId || entry.firestoreId === billId
  );
  if (localMatch) {
    return localBillToHistoryEntry(localMatch);
  }

  return null;
}

export { markLocalBillSynced, persistLocalBill } from "./localBillStore";
