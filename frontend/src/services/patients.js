import { Capacitor } from "@capacitor/core";
import {
  collection,
  deleteDoc,
  doc,
  getDoc,
  getDocsFromServer,
  serverTimestamp,
  setDoc,
} from "firebase/firestore";
import { ensureFirebaseWebAuth } from "../auth/ensureFirebaseWebAuth";
import { auth, awaitFirestoreReady, db } from "../firebase";
import { deleteBillsForPatientIds, getBillsForPatientIds } from "./bills";
import { deleteHistoricalDocumentsForPatientIds } from "./patientHistoricalDocuments";
import { deleteHospitalsForPatientIds } from "./patientHospitals";
import { normalizeClinicalHistory } from "../utils/clinicalHistory";
import { validateBirthYearInput } from "../utils/patientAge";
import {
  getLocalPatientById,
  getLocalPatients,
  getUnsyncedLocalPatients,
  localPatientToEntry,
  markLocalPatientSynced,
  persistLocalPatient,
  removeLocalPatient,
} from "./localPatientStore";

const FIRESTORE_TIMEOUT_MS = Capacitor.isNativePlatform() ? 15000 : 5000;

function patientsCollection(userId) {
  return collection(db, "users", userId, "patients");
}

function patientDocRef(userId, patientId) {
  return doc(db, "users", userId, "patients", patientId);
}

function withTimeout(promise, ms = FIRESTORE_TIMEOUT_MS) {
  return Promise.race([
    promise,
    new Promise((_, reject) => {
      window.setTimeout(
        () => reject(new Error("Cloud save timed out. Patient is saved on this device.")),
        ms
      );
    }),
  ]);
}

function firebaseErrorMessage(error) {
  const code = error?.code || "";
  if (code === "permission-denied") {
    return (
      "Cloud save blocked (permission denied). Patient is saved on this device. " +
      "Ask your admin to deploy Firestore rules: firebase deploy --only firestore:rules"
    );
  }
  if (code === "unavailable") {
    return "Cloud is unavailable. Patient is saved on this device.";
  }
  return error?.message || "Cloud save failed. Patient is saved on this device.";
}

export function validatePatientInput(patientData) {
  const name = patientData?.name?.trim() || "";
  if (!name) {
    throw new Error("Please enter the patient name.");
  }
  const gender = patientData?.gender || "";
  if (!gender) {
    throw new Error("Please select a gender.");
  }
  const birthYear = validateBirthYearInput(patientData?.birthYear);
  const state = patientData?.state?.trim() || "";
  const city = patientData?.city?.trim() || "";
  return {
    name,
    gender,
    birthYear,
    state,
    city,
    savePastBills: patientData?.savePastBills === true,
    clinicalHistory: normalizeClinicalHistory(patientData?.clinicalHistory),
  };
}

function mergePatientLists(cloudPatients, localEntries) {
  const cloudIds = new Set(cloudPatients.map((p) => p.id));
  const merged = [...cloudPatients];

  for (const entry of localEntries) {
    const publicId = entry.firestoreId || entry.localId;
    if (entry.firestoreId && cloudIds.has(entry.firestoreId)) {
      continue;
    }
    if (!merged.some((p) => p.id === publicId || p.localId === entry.localId)) {
      merged.push(localPatientToEntry(entry));
    }
  }

  return merged.sort((a, b) => {
    const nameA = (a.name || "").toLowerCase();
    const nameB = (b.name || "").toLowerCase();
    return nameA.localeCompare(nameB);
  });
}

function buildFirestorePayload(patientData) {
  const validated = validatePatientInput(patientData);
  return {
    name: validated.name,
    birthYear: validated.birthYear,
    gender: validated.gender,
    state: validated.state,
    city: validated.city,
    savePastBills: validated.savePastBills,
    clinicalHistory: validated.clinicalHistory,
    updatedAt: serverTimestamp(),
  };
}

async function fetchCloudPatients(userId) {
  await ensureFirebaseWebAuth();
  await awaitFirestoreReady();
  if (!auth.currentUser) {
    throw Object.assign(new Error("Firebase session expired. Sign out and sign in again."), {
      code: "auth/user-not-found",
    });
  }

  const snapshot = await getDocsFromServer(patientsCollection(userId));
  return snapshot.docs.map((entry) => ({
    id: entry.id,
    firestoreId: entry.id,
    localOnly: false,
    ...entry.data(),
  }));
}

async function pushPatientToCloud(userId, patientId, patientData, isNew) {
  const payload = buildFirestorePayload(patientData);
  if (isNew) {
    payload.createdAt = serverTimestamp();
  }
  await withTimeout(
    setDoc(patientDocRef(userId, patientId), payload, { merge: true })
  );
  markLocalPatientSynced(userId, patientId, patientId);
  return patientId;
}

export async function syncPendingPatients(userId) {
  const pending = getUnsyncedLocalPatients(userId);
  let syncedCount = 0;

  for (const entry of pending) {
    try {
      await pushPatientToCloud(userId, entry.localId, entry.patientData, true);
      syncedCount += 1;
    } catch (error) {
      console.error("Failed to sync local patient to Firebase:", error);
    }
  }

  return syncedCount;
}

export function getPatientsLocalSnapshot(userId) {
  if (!userId) {
    return [];
  }
  return mergePatientLists([], getLocalPatients(userId));
}

function patientCloudSyncWarning(error) {
  const code = error?.code || "";
  if (code === "auth/user-not-found") {
    return error.message;
  }
  if (code === "permission-denied") {
    return (
      "Could not load patients from your account (permission denied). " +
      "Deploy Firestore rules: npm run deploy:firestore-rules"
    );
  }
  if (code === "unavailable") {
    return "Could not reach Firebase. Showing patients saved on this device.";
  }
  const message = error?.message || "";
  if (/timed out/i.test(message)) {
    return "Account sync is slow. Showing patients saved on this device.";
  }
  return "Could not sync patients from your account. Showing data saved on this device.";
}

export async function getPatients(userId) {
  const { patients } = await getPatientsWithSyncStatus(userId);
  return patients;
}

export async function getPatientsWithSyncStatus(userId) {
  if (!userId) {
    return { patients: [], cloudWarning: null };
  }

  const localEntries = getLocalPatients(userId);

  let cloudPatients = [];
  let cloudWarning = null;
  try {
    cloudPatients = await withTimeout(fetchCloudPatients(userId), FIRESTORE_TIMEOUT_MS);
  } catch (error) {
    console.error("Failed to load patients from Firebase:", error);
    cloudWarning = patientCloudSyncWarning(error);
  }

  const patients = mergePatientLists(cloudPatients, localEntries);

  syncPendingPatients(userId).catch((error) => {
    console.error("Background patient sync failed:", error);
  });

  return {
    patients,
    cloudWarning,
  };
}

function collectPatientIdVariants(userId, patientId) {
  const ids = new Set([patientId]);
  const local = getLocalPatientById(userId, patientId);
  if (local) {
    if (local.id) {
      ids.add(local.id);
    }
    if (local.localId) {
      ids.add(local.localId);
    }
    if (local.firestoreId) {
      ids.add(local.firestoreId);
    }
  }
  return [...ids];
}

export async function getPatient(userId, patientId) {
  if (!userId || !patientId) {
    return null;
  }

  const local = getLocalPatientById(userId, patientId);
  if (local) {
    return local;
  }

  try {
    await awaitFirestoreReady();
    const snapshot = await getDoc(patientDocRef(userId, patientId));
    if (snapshot.exists()) {
      return {
        id: snapshot.id,
        firestoreId: snapshot.id,
        localOnly: false,
        ...snapshot.data(),
      };
    }
  } catch (error) {
    console.error("Failed to load patient from Firebase:", error);
  }

  return null;
}

export async function createPatient(userId, patientData) {
  if (!userId) {
    throw new Error("You must be signed in to save a patient.");
  }

  const validated = validatePatientInput(patientData);

  let localId;
  try {
    localId = persistLocalPatient(userId, validated);
  } catch (error) {
    throw new Error(
      `Could not save on this device: ${error?.message || "storage error"}`
    );
  }

  const localEntry = getLocalPatients(userId).find((e) => e.localId === localId);
  const savedEntry = localEntry
    ? localPatientToEntry(localEntry)
    : {
        id: localId,
        localId,
        firestoreId: null,
        localOnly: true,
        ...validated,
      };

  pushPatientToCloud(userId, localId, validated, true).catch((error) => {
    console.error("Background patient cloud sync failed:", error);
  });

  return {
    id: localId,
    localId,
    patient: savedEntry,
    synced: false,
    warning: null,
  };
}

export async function updatePatient(userId, patientId, patientData) {
  if (!userId) {
    throw new Error("You must be signed in to update a patient.");
  }

  const validated = validatePatientInput(patientData);
  const localEntries = getLocalPatients(userId);
  const localMatch = localEntries.find(
    (entry) => entry.localId === patientId || entry.firestoreId === patientId
  );
  const localId = localMatch?.localId || patientId;

  persistLocalPatient(userId, validated, localId);

  try {
    const cloudId = await pushPatientToCloud(
      userId,
      localMatch?.firestoreId || localId,
      validated,
      !localMatch?.firestoreId
    );
    return { id: cloudId, warning: null };
  } catch (error) {
    console.error("Firebase updatePatient failed:", error);
    return { id: localId, warning: firebaseErrorMessage(error) };
  }
}

export async function deletePatient(userId, patientId) {
  if (!userId || !patientId) {
    throw new Error("Missing patient or user.");
  }

  const patientIds = collectPatientIdVariants(userId, patientId);
  await deleteBillsForPatientIds(userId, patientIds);
  await deleteHistoricalDocumentsForPatientIds(userId, patientIds);
  await deleteHospitalsForPatientIds(userId, patientIds);

  const localEntries = getLocalPatients(userId);
  const localMatch = localEntries.find(
    (entry) => entry.localId === patientId || entry.firestoreId === patientId
  );
  const firestoreId = localMatch?.firestoreId || patientId;

  try {
    await withTimeout(deleteDoc(patientDocRef(userId, firestoreId)));
  } catch (error) {
    const code = error?.code || "";
    if (code === "permission-denied") {
      throw new Error(firebaseErrorMessage(error));
    }
    if (code !== "not-found") {
      console.error("Cloud patient delete failed:", error);
    }
  }

  removeLocalPatient(userId, patientId);
}

export async function getPatientBills(userId, patientId) {
  if (!userId || !patientId) {
    return [];
  }

  const patientIds = collectPatientIdVariants(userId, patientId);
  return getBillsForPatientIds(userId, patientIds);
}
