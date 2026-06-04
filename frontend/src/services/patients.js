import {
  collection,
  deleteDoc,
  doc,
  getDoc,
  getDocs,
  serverTimestamp,
  setDoc,
} from "firebase/firestore";
import { db } from "../firebase";
import { deleteBillsForPatientIds, getBillsForPatientIds } from "./bills";
import {
  getLocalPatientById,
  getLocalPatients,
  getUnsyncedLocalPatients,
  localPatientToEntry,
  markLocalPatientSynced,
  persistLocalPatient,
  removeLocalPatient,
} from "./localPatientStore";

const FIRESTORE_TIMEOUT_MS = 5000;

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
  const age = Number(patientData?.age);
  if (!Number.isFinite(age) || age < 0 || age > 150) {
    throw new Error("Please enter a valid age (0–150).");
  }
  return { name, gender, age, ayushmanEligible: Boolean(patientData?.ayushmanEligible) };
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
    age: validated.age,
    gender: validated.gender,
    ayushmanEligible: validated.ayushmanEligible,
    updatedAt: serverTimestamp(),
  };
}

async function fetchCloudPatients(userId) {
  const snapshot = await getDocs(patientsCollection(userId));
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

export async function getPatients(userId) {
  if (!userId) {
    return [];
  }

  const localEntries = getLocalPatients(userId);

  let cloudPatients = [];
  try {
    cloudPatients = await withTimeout(fetchCloudPatients(userId), FIRESTORE_TIMEOUT_MS);
  } catch (error) {
    console.error("Failed to load patients from Firebase:", error);
  }

  syncPendingPatients(userId).catch((error) => {
    console.error("Background patient sync failed:", error);
  });

  return mergePatientLists(cloudPatients, localEntries);
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

  // Save to device first (instant). Cloud sync runs in background.
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
  const patientIds = collectPatientIdVariants(userId, patientId);
  await deleteBillsForPatientIds(userId, patientIds);

  const localEntries = getLocalPatients(userId);
  const localMatch = localEntries.find(
    (entry) => entry.localId === patientId || entry.firestoreId === patientId
  );
  const firestoreId = localMatch?.firestoreId || patientId;

  removeLocalPatient(userId, patientId);

  try {
    await withTimeout(deleteDoc(patientDocRef(userId, firestoreId)));
  } catch (error) {
    const localStill = getLocalPatientById(userId, patientId);
    if (localStill) {
      throw new Error(firebaseErrorMessage(error));
    }
  }
}

export async function getPatientBills(userId, patientId) {
  if (!userId || !patientId) {
    return [];
  }

  const patientIds = collectPatientIdVariants(userId, patientId);
  return getBillsForPatientIds(userId, patientIds);
}
