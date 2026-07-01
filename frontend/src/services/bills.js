import {
  addDoc,
  collection,
  deleteDoc,
  doc,
  getDoc,
  getDocs,
  query,
  serverTimestamp,
  where,
} from "firebase/firestore";
import { db } from "../firebase";
import {
  getLocalBillById,
  getLocalBills,
  getUnsyncedLocalBills,
  localBillToHistoryEntry,
  markLocalBillSynced,
  persistLocalBill,
  removeLocalBill,
  removeLocalBillsForPatientIds,
} from "./localBillStore";
import { getLocalMedicalHistoryConsent } from "./localMedicalHistoryConsentStore";
import { canSaveMedicalHistory } from "../utils/medicalHistoryConsent";
import { getPatientAge, getPatientBirthYear } from "../utils/patientAge";

function billsCollection(userId) {
  return collection(db, "users", userId, "bills");
}

function isFirestoreSpecialValue(value) {
  if (!value || typeof value !== "object") {
    return false;
  }
  if (typeof value.toDate === "function") {
    return true;
  }
  if (typeof value._methodName === "string") {
    return true;
  }
  if (value.constructor?.name === "FieldValue") {
    return true;
  }
  return false;
}

export function sanitizeForFirestore(value) {
  if (value === undefined) {
    return undefined;
  }
  if (value === null || typeof value !== "object") {
    return value;
  }
  if (isFirestoreSpecialValue(value)) {
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

function mapCloudBillDocs(docs) {
  return docs.map((entry) => ({
    id: entry.id,
    firestoreId: entry.id,
    localOnly: false,
    ...entry.data(),
  }));
}

async function fetchCloudBills(userId) {
  const snapshot = await getDocs(billsCollection(userId));
  return mapCloudBillDocs(snapshot.docs);
}

async function fetchCloudBillsForPatientIds(userId, patientIds) {
  const ids = [...new Set(patientIds.filter(Boolean))].slice(0, 10);
  if (!ids.length) {
    return [];
  }
  const snapshot = await getDocs(
    query(billsCollection(userId), where("patientId", "in", ids))
  );
  return mapCloudBillDocs(snapshot.docs);
}

function filterLocalBillEntries(userId, patientIds) {
  const idSet = new Set(patientIds.filter(Boolean));
  if (!idSet.size) {
    return [];
  }
  return getLocalBills(userId).filter((entry) => {
    const data = entry.billData || {};
    return idSet.has(data.patientId) || idSet.has(data.patient?.id);
  });
}

export function getUserBillsLocalSnapshot(userId) {
  if (!userId) {
    return [];
  }
  const localEntries = getLocalBills(userId);
  return sortBillsNewestFirst(
    localEntries.map((entry) => localBillToHistoryEntry(entry))
  );
}

function mergeBillLists(cloudBills, localEntries) {
  const cloudIds = new Set(cloudBills.map((bill) => bill.id));
  const cloudClientIds = new Set(
    cloudBills.map((bill) => bill.clientId).filter(Boolean)
  );
  const merged = [...cloudBills];

  for (const entry of localEntries) {
    if (entry.firestoreId && cloudIds.has(entry.firestoreId)) {
      continue;
    }
    if (cloudClientIds.has(entry.localId)) {
      continue;
    }
    const publicId = entry.firestoreId || entry.localId;
    if (!merged.some((bill) => bill.id === publicId)) {
      merged.push(localBillToHistoryEntry(entry));
    }
  }

  return merged;
}

export function buildReportSavePayload(reportData, patient) {
  if (!patient) {
    return reportData;
  }
  return {
    ...reportData,
    patientId: patient.id || null,
    patient: {
      id: patient.id,
      name: patient.name,
      birthYear: getPatientBirthYear(patient),
      age: getPatientAge(patient),
      gender: patient.gender,
    },
  };
}

export async function saveReportToAccount(userId, patient, reportData, options = {}) {
  if (!userId || !patient) {
    return { saved: false };
  }

  const accountConsent =
    options.accountConsent ?? getLocalMedicalHistoryConsent(userId);
  if (!canSaveMedicalHistory(accountConsent, patient)) {
    return { saved: false, reason: "consent_required" };
  }

  const payload = buildReportSavePayload(reportData, patient);
  const localId = persistLocalBill(userId, payload);

  try {
    const firestoreId = await saveBill(userId, payload, {
      localId,
      patientId: patient.id || null,
    });
    markLocalBillSynced(userId, localId, firestoreId);
    return { saved: true, localId, firestoreId, localOnly: false };
  } catch (error) {
    console.error("Failed to sync report to Firebase:", error);
    return { saved: true, localId, localOnly: true, error };
  }
}

export async function saveBill(userId, billData, options = {}) {
  const payload = sanitizeForFirestore({
    ...billData,
    patientId: options.patientId || billData.patientId || billData.patient?.id || null,
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

export function getPendingBillSyncMessage(pendingCount) {
  if (pendingCount <= 0) {
    return "";
  }
  const label = `${pendingCount} bill${pendingCount === 1 ? "" : "s"} saved on this device`;
  const offline = typeof navigator !== "undefined" && !navigator.onLine;
  if (offline) {
    return `${label} — will sync when you're back online.`;
  }
  return `${label} — couldn't reach your account. Reopen this page to retry.`;
}

export async function getUserBills(userId) {
  if (!userId) {
    return [];
  }

  try {
    await syncPendingBills(userId);
  } catch (error) {
    console.error("Background bill sync failed:", error);
  }

  let cloudBills = [];
  try {
    cloudBills = await fetchCloudBills(userId);
  } catch (error) {
    console.error("Failed to load bills from Firebase:", error);
  }

  const localEntries = getLocalBills(userId);
  const merged = mergeBillLists(cloudBills, localEntries);
  return sortBillsNewestFirst(merged);
}

export async function getBillsForPatientIds(userId, patientIds) {
  if (!userId || !patientIds?.length) {
    return [];
  }

  const ids = [...new Set(patientIds.filter(Boolean))];
  const localEntries = filterLocalBillEntries(userId, ids);

  let cloudBills = [];
  try {
    cloudBills = await fetchCloudBillsForPatientIds(userId, ids);
  } catch (error) {
    console.error("Failed to load patient bills from Firebase:", error);
  }

  return sortBillsNewestFirst(mergeBillLists(cloudBills, localEntries));
}

export async function getBill(userId, billId) {
  if (!userId || !billId) {
    return null;
  }

  const local = getLocalBillById(userId, billId);
  if (local) {
    return local;
  }

  try {
    const billRef = doc(db, "users", userId, "bills", billId);
    const snapshot = await getDoc(billRef);
    if (snapshot.exists()) {
      return {
        id: snapshot.id,
        firestoreId: snapshot.id,
        localOnly: false,
        ...snapshot.data(),
      };
    }
  } catch (error) {
    console.error("Failed to load bill from Firebase:", error);
  }

  return null;
}

export async function deleteBillsForPatientIds(userId, patientIds) {
  if (!userId || !patientIds?.length) {
    return 0;
  }

  const ids = [...new Set(patientIds.filter(Boolean))];
  const bills = await getBillsForPatientIds(userId, ids);
  const cloudIds = new Set();

  for (const bill of bills) {
    const cloudId = bill.firestoreId || (!bill.localOnly ? bill.id : null);
    if (cloudId) {
      cloudIds.add(cloudId);
    }
  }

  await Promise.all(
    [...cloudIds].map((cloudId) =>
      deleteDoc(doc(db, "users", userId, "bills", cloudId)).catch((error) => {
        console.error("Failed to delete bill from Firebase:", error);
      })
    )
  );

  removeLocalBillsForPatientIds(userId, ids);
  return bills.length;
}

export async function deleteBill(userId, billId) {
  if (!userId || !billId) {
    throw new Error("Missing bill or user.");
  }

  const bill = await getBill(userId, billId);
  if (!bill) {
    throw new Error("Bill not found.");
  }

  const cloudId = bill.firestoreId || (!bill.localOnly ? bill.id : null);
  if (cloudId) {
    try {
      await deleteDoc(doc(db, "users", userId, "bills", cloudId));
    } catch (error) {
      console.error("Failed to delete bill from Firebase:", error);
      const stillLocal = getLocalBillById(userId, billId);
      if (!stillLocal) {
        throw new Error("Could not delete bill from your account. Try again when online.");
      }
    }
  }

  removeLocalBill(userId, billId);
  if (cloudId && cloudId !== billId) {
    removeLocalBill(userId, cloudId);
  }
}

export { markLocalBillSynced, persistLocalBill } from "./localBillStore";
