import {
  collection,
  deleteDoc,
  doc,
  getDocs,
  serverTimestamp,
  setDoc,
} from "firebase/firestore";
import { awaitFirestoreReady, db } from "../firebase";
import { resolveCanonicalStateUtName } from "./locations";
import { getSecureJson, setSecureJson } from "./secureLocalStore";

const STORAGE_KEY = "swaasth_local_hospitals_v1";

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

function hospitalsCollection(userId, patientId) {
  return collection(db, "users", userId, "patients", patientId, "hospitals");
}

function hospitalDocRef(userId, patientId, hospitalId) {
  return doc(db, "users", userId, "patients", patientId, "hospitals", hospitalId);
}

function localHospitalToEntry(entry) {
  return {
    id: entry.firestoreId || entry.localId,
    localId: entry.localId,
    firestoreId: entry.firestoreId || null,
    localOnly: !entry.firestoreId,
    ...entry.hospitalData,
  };
}

function sortByName(hospitals) {
  return [...hospitals].sort((left, right) => {
    const nameA = (left.name || "").toLowerCase();
    const nameB = (right.name || "").toLowerCase();
    return nameA.localeCompare(nameB);
  });
}

function collectPatientIdSet(patientIds) {
  return new Set(patientIds.filter(Boolean));
}

export function validateHospitalInput(hospitalData) {
  const name = hospitalData?.name?.trim() || "";
  if (!name) {
    throw new Error("Please enter the hospital name.");
  }
  const state = resolveCanonicalStateUtName(hospitalData?.state || "");
  if (!state) {
    throw new Error("Please select a state/UT.");
  }
  const city = hospitalData?.city?.trim() || "";
  if (!city) {
    throw new Error("Please select a city.");
  }
  return { name, state, city };
}

export function getLocalHospitals(userId, patientIds) {
  const idSet = collectPatientIdSet(patientIds);
  if (!userId || !idSet.size) {
    return [];
  }
  const entries = readStore().users[userId] || [];
  return sortByName(
    entries
      .filter((entry) => idSet.has(entry.hospitalData?.patientId))
      .map((entry) => localHospitalToEntry(entry))
  );
}

export function getLocalHospitalsSnapshot(userId, patientId) {
  if (!userId || !patientId) {
    return [];
  }
  return getLocalHospitals(userId, [patientId]);
}

async function fetchCloudHospitals(userId, patientIds) {
  await awaitFirestoreReady();
  const ids = [...collectPatientIdSet(patientIds)].slice(0, 10);
  if (!ids.length) {
    return [];
  }

  const results = [];
  for (const patientId of ids) {
    try {
      const snapshot = await getDocs(hospitalsCollection(userId, patientId));
      for (const entry of snapshot.docs) {
        results.push({
          id: entry.id,
          firestoreId: entry.id,
          localOnly: false,
          patientId,
          ...entry.data(),
        });
      }
    } catch (error) {
      console.error("Failed to load hospitals from Firebase:", error);
    }
  }
  return sortByName(results);
}

function mergeHospitalLists(cloudHospitals, localEntries) {
  const cloudIds = new Set(cloudHospitals.map((hospital) => hospital.id));
  const merged = [...cloudHospitals];

  for (const entry of localEntries) {
    if (entry.firestoreId && cloudIds.has(entry.firestoreId)) {
      continue;
    }
    const publicId = entry.firestoreId || entry.localId;
    if (!merged.some((hospital) => hospital.id === publicId)) {
      merged.push(entry);
    }
  }

  return sortByName(merged);
}

export async function getPatientHospitals(userId, patientId) {
  if (!userId || !patientId) {
    return [];
  }

  const localEntries = getLocalHospitals(userId, [patientId]);
  let cloudHospitals = [];
  try {
    cloudHospitals = await fetchCloudHospitals(userId, [patientId]);
  } catch (error) {
    console.error("Failed to fetch cloud hospitals:", error);
  }

  return mergeHospitalLists(cloudHospitals, localEntries);
}

function persistLocalHospital(userId, hospitalData) {
  const store = readStore();
  const entries = userEntries(store, userId);
  const localId =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `local-hosp-${Date.now()}-${Math.random().toString(36).slice(2)}`;

  entries.push({
    localId,
    hospitalData,
    synced: false,
    firestoreId: null,
    updatedAt: Date.now(),
  });
  writeStore(store);
  return localId;
}

function markLocalHospitalSynced(userId, localId, firestoreId) {
  const store = readStore();
  const entries = store.users[userId] || [];
  const entry = entries.find((item) => item.localId === localId);
  if (entry) {
    entry.firestoreId = firestoreId;
    entry.synced = true;
    writeStore(store);
  }
}

function updateLocalHospital(userId, hospitalId, hospitalData) {
  const store = readStore();
  const entries = store.users[userId] || [];
  const entry = entries.find(
    (item) => item.localId === hospitalId || item.firestoreId === hospitalId
  );
  if (entry) {
    entry.hospitalData = hospitalData;
    entry.synced = false;
    entry.updatedAt = Date.now();
    writeStore(store);
    return entry.localId;
  }
  return persistLocalHospital(userId, hospitalData);
}

function removeLocalHospital(userId, hospitalId) {
  const store = readStore();
  const entries = store.users[userId] || [];
  store.users[userId] = entries.filter(
    (entry) => entry.localId !== hospitalId && entry.firestoreId !== hospitalId
  );
  writeStore(store);
}

async function pushHospitalToCloud(userId, patientId, hospitalId, hospitalData) {
  const payload = {
    ...hospitalData,
    updatedAt: serverTimestamp(),
    createdAt: serverTimestamp(),
  };
  await setDoc(hospitalDocRef(userId, patientId, hospitalId), payload, {
    merge: true,
  });
  markLocalHospitalSynced(userId, hospitalId, hospitalId);
}

export async function createHospital(userId, patientId, hospitalData) {
  if (!userId || !patientId) {
    throw new Error("Missing user or patient.");
  }

  const validated = validateHospitalInput(hospitalData);
  const data = { ...validated, patientId };
  const localId = persistLocalHospital(userId, data);

  pushHospitalToCloud(userId, patientId, localId, data).catch((error) => {
    console.error("Background hospital cloud sync failed:", error);
  });

  return {
    id: localId,
    localId,
    localOnly: true,
    ...data,
  };
}

export async function updateHospital(userId, patientId, hospitalId, hospitalData) {
  if (!userId || !patientId || !hospitalId) {
    throw new Error("Missing hospital details.");
  }

  const validated = validateHospitalInput(hospitalData);
  const data = { ...validated, patientId };
  const localId = updateLocalHospital(userId, hospitalId, data);

  try {
    await pushHospitalToCloud(userId, patientId, hospitalId, data);
    return { id: hospitalId, warning: null };
  } catch (error) {
    console.error("Firebase updateHospital failed:", error);
    return { id: localId, warning: "Hospital saved on this device. Cloud sync will retry." };
  }
}

export async function deleteHospital(userId, patientId, hospitalId) {
  if (!userId || !patientId || !hospitalId) {
    throw new Error("Missing hospital details.");
  }

  removeLocalHospital(userId, hospitalId);

  try {
    await deleteDoc(hospitalDocRef(userId, patientId, hospitalId));
  } catch (error) {
    const code = error?.code || "";
    if (code !== "not-found") {
      console.error("Cloud hospital delete failed:", error);
    }
  }
}

export async function deleteHospitalsForPatientIds(userId, patientIds) {
  if (!userId) {
    return;
  }
  const hospitals = getLocalHospitals(userId, patientIds);
  for (const entry of hospitals) {
    removeLocalHospital(userId, entry.id);
  }

  for (const patientId of patientIds) {
    try {
      await awaitFirestoreReady();
      const snapshot = await getDocs(hospitalsCollection(userId, patientId));
      await Promise.all(snapshot.docs.map((entry) => deleteDoc(entry.ref)));
    } catch (error) {
      console.error("Failed to delete cloud hospitals:", error);
    }
  }
}

export function clearLocalHospitalsForUser(userId) {
  if (!userId) {
    return;
  }
  const store = readStore();
  if (store.users[userId]) {
    delete store.users[userId];
    writeStore(store);
  }
}

export function resolveHospitalLocation(hospital) {
  if (!hospital) {
    return { state: "", city: "", name: "" };
  }
  return {
    state: resolveCanonicalStateUtName(hospital.state || ""),
    city: String(hospital.city || "").trim(),
    name: String(hospital.name || "").trim(),
  };
}
