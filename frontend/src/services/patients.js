import { Capacitor } from "@capacitor/core";
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

function normalizeKcrKitFields(patientData, age = Number(patientData?.age)) {
  const selected = Boolean(patientData?.kcrKitSelected);
  const ageEligible = Number.isFinite(age) && age >= 18;
  if (!selected || !ageEligible) {
    return {
      kcrKitSelected: false,
      kcrIsPregnant: false,
      kcrIsTelanganaResident: false,
      kcrAge18OrAbove: false,
      kcrIncomeBelow10000: false,
      kcrGovernmentHospitalTreatment: false,
      kcrMoreThanTwoLiveChildren: false,
      kcrAadhaarTelangana: false,
      kcrIdentifiedByAnganwadiWorker: false,
    };
  }
  return {
    kcrKitSelected: true,
    kcrIsPregnant: Boolean(patientData?.kcrIsPregnant),
    kcrIsTelanganaResident: Boolean(patientData?.kcrIsTelanganaResident),
    kcrAge18OrAbove: true,
    kcrIncomeBelow10000: Boolean(patientData?.kcrIncomeBelow10000),
    kcrGovernmentHospitalTreatment: Boolean(
      patientData?.kcrGovernmentHospitalTreatment
    ),
    kcrMoreThanTwoLiveChildren: Boolean(
      patientData?.kcrMoreThanTwoLiveChildren
    ),
    kcrAadhaarTelangana: Boolean(patientData?.kcrAadhaarTelangana),
    kcrIdentifiedByAnganwadiWorker: Boolean(
      patientData?.kcrIdentifiedByAnganwadiWorker
    ),
  };
}

function normalizeEhsFields(patientData) {
  const selected = Boolean(patientData?.ehsSelected);
  if (!selected) {
    return {
      ehsSelected: false,
      ehsIsGovernmentEmployee: false,
      ehsIsPensioner: false,
      ehsIsDependent: false,
      ehsHasHealthCard: false,
      ehsCardNumber: null,
    };
  }
  const cardNumber = String(patientData?.ehsCardNumber || "").trim();
  return {
    ehsSelected: true,
    ehsIsGovernmentEmployee: Boolean(patientData?.ehsIsGovernmentEmployee),
    ehsIsPensioner: Boolean(patientData?.ehsIsPensioner),
    ehsIsDependent: Boolean(patientData?.ehsIsDependent),
    ehsHasHealthCard: Boolean(patientData?.ehsHasHealthCard),
    ehsCardNumber: cardNumber || null,
  };
}

function normalizeJhsFields(patientData) {
  const selected = Boolean(patientData?.jhsSelected);
  if (!selected) {
    return {
      jhsSelected: false,
      jhsIsWorkingJournalist: false,
      jhsIsRetiredJournalist: false,
      jhsIsDependent: false,
      jhsHasHealthCard: false,
      jhsHasAadhaar: false,
      jhsCardNumber: null,
    };
  }
  const cardNumber = String(patientData?.jhsCardNumber || "").trim();
  return {
    jhsSelected: true,
    jhsIsWorkingJournalist: Boolean(patientData?.jhsIsWorkingJournalist),
    jhsIsRetiredJournalist: Boolean(patientData?.jhsIsRetiredJournalist),
    jhsIsDependent: Boolean(patientData?.jhsIsDependent),
    jhsHasHealthCard: Boolean(patientData?.jhsHasHealthCard),
    jhsHasAadhaar: Boolean(patientData?.jhsHasAadhaar),
    jhsCardNumber: cardNumber || null,
  };
}

function normalizeRajivAarogyasriFields(patientData) {
  const selected = Boolean(patientData?.rajivAarogyasriSelected);
  if (!selected) {
    return {
      rajivAarogyasriSelected: false,
      rajivIsTelanganaResident: false,
      rajivHasEligibleCard: false,
      rajivHasAadhaar: false,
      rajivIsCancerRelated: false,
      rajivFamilyCoverageUsedAmount: null,
    };
  }

  const rawAmount = patientData?.rajivFamilyCoverageUsedAmount;
  let familyAmount = null;
  if (rawAmount !== "" && rawAmount != null) {
    const parsed = Number(rawAmount);
    if (Number.isFinite(parsed) && parsed >= 0) {
      familyAmount = parsed;
    }
  }

  return {
    rajivAarogyasriSelected: true,
    rajivIsTelanganaResident: Boolean(patientData?.rajivIsTelanganaResident),
    rajivHasEligibleCard: Boolean(patientData?.rajivHasEligibleCard),
    rajivHasAadhaar: Boolean(patientData?.rajivHasAadhaar),
    rajivIsCancerRelated: Boolean(patientData?.rajivIsCancerRelated),
    rajivFamilyCoverageUsedAmount: familyAmount,
  };
}

function deriveCghsEligibleCategoryConfirmed(category) {
  if (!category) {
    return null;
  }
  if (category === "not_sure") {
    return false;
  }
  return true;
}

function normalizeCghsEligibilityFields(patientData) {
  const category = String(patientData?.cghsBeneficiaryCategory || "").trim();
  const resides = patientData?.cghsResidesInCoveredCity;
  const residesInCoveredCity =
    resides === true || resides === false ? resides : null;

  return {
    cghsBeneficiaryCategory: category || null,
    cghsEligibleCategoryConfirmed: deriveCghsEligibleCategoryConfirmed(category),
    cghsResidesInCoveredCity: residesInCoveredCity,
  };
}

function normalizePmjayFields(patientData) {
  const selected = Boolean(patientData?.ayushmanEligible);
  if (!selected) {
    return {
      pmjayHasAyushmanCard: null,
    };
  }
  const card = patientData?.pmjayHasAyushmanCard;
  return {
    pmjayHasAyushmanCard: card === true || card === false ? card : null,
  };
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
  const state = patientData?.state?.trim() || "";
  const kcrFields = normalizeKcrKitFields(patientData, age);
  const rajivFields = normalizeRajivAarogyasriFields(patientData);
  const ehsFields = normalizeEhsFields(patientData);
  const jhsFields = normalizeJhsFields(patientData);
  const cghsFields = normalizeCghsEligibilityFields(patientData);
  const pmjayFields = normalizePmjayFields(patientData);
  return {
    name,
    gender,
    age,
    state,
    ayushmanEligible: Boolean(patientData?.ayushmanEligible),
    aarogyaBhadrathaEligible: Boolean(patientData?.aarogyaBhadrathaEligible),
    hospitalisationReliefSchemeSelected: Boolean(
      patientData?.hospitalisationReliefSchemeSelected
    ),
    isRegisteredConstructionWorker: Boolean(
      patientData?.hospitalisationReliefSchemeSelected &&
        patientData?.isRegisteredConstructionWorker
    ),
    ...kcrFields,
    ...rajivFields,
    ...ehsFields,
    ...jhsFields,
    ...cghsFields,
    ...pmjayFields,
    savePastBills: Boolean(patientData?.savePastBills),
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
    age: validated.age,
    gender: validated.gender,
    state: validated.state,
    ayushmanEligible: validated.ayushmanEligible,
    aarogyaBhadrathaEligible: validated.aarogyaBhadrathaEligible,
    hospitalisationReliefSchemeSelected:
      validated.hospitalisationReliefSchemeSelected,
    isRegisteredConstructionWorker: validated.isRegisteredConstructionWorker,
    kcrKitSelected: validated.kcrKitSelected,
    kcrIsPregnant: validated.kcrIsPregnant,
    kcrIsTelanganaResident: validated.kcrIsTelanganaResident,
    kcrAge18OrAbove: validated.kcrAge18OrAbove,
    kcrIncomeBelow10000: validated.kcrIncomeBelow10000,
    kcrGovernmentHospitalTreatment: validated.kcrGovernmentHospitalTreatment,
    kcrMoreThanTwoLiveChildren: validated.kcrMoreThanTwoLiveChildren,
    kcrAadhaarTelangana: validated.kcrAadhaarTelangana,
    kcrIdentifiedByAnganwadiWorker: validated.kcrIdentifiedByAnganwadiWorker,
    rajivAarogyasriSelected: validated.rajivAarogyasriSelected,
    rajivIsTelanganaResident: validated.rajivIsTelanganaResident,
    rajivHasEligibleCard: validated.rajivHasEligibleCard,
    rajivHasAadhaar: validated.rajivHasAadhaar,
    rajivIsCancerRelated: validated.rajivIsCancerRelated,
    rajivFamilyCoverageUsedAmount: validated.rajivFamilyCoverageUsedAmount,
    ehsSelected: validated.ehsSelected,
    ehsIsGovernmentEmployee: validated.ehsIsGovernmentEmployee,
    ehsIsPensioner: validated.ehsIsPensioner,
    ehsIsDependent: validated.ehsIsDependent,
    ehsHasHealthCard: validated.ehsHasHealthCard,
    ehsCardNumber: validated.ehsCardNumber,
    jhsSelected: validated.jhsSelected,
    jhsIsWorkingJournalist: validated.jhsIsWorkingJournalist,
    jhsIsRetiredJournalist: validated.jhsIsRetiredJournalist,
    jhsIsDependent: validated.jhsIsDependent,
    jhsHasHealthCard: validated.jhsHasHealthCard,
    jhsHasAadhaar: validated.jhsHasAadhaar,
    jhsCardNumber: validated.jhsCardNumber,
    cghsBeneficiaryCategory: validated.cghsBeneficiaryCategory,
    cghsEligibleCategoryConfirmed: validated.cghsEligibleCategoryConfirmed,
    cghsResidesInCoveredCity: validated.cghsResidesInCoveredCity,
    pmjayHasAyushmanCard: validated.pmjayHasAyushmanCard,
    savePastBills: validated.savePastBills,
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

function patientCloudSyncWarning(error) {
  const code = error?.code || "";
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

  syncPendingPatients(userId).catch((error) => {
    console.error("Background patient sync failed:", error);
  });

  return {
    patients: mergePatientLists(cloudPatients, localEntries),
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
  if (!userId || !patientId) {
    throw new Error("Missing patient or user.");
  }

  const patientIds = collectPatientIdVariants(userId, patientId);
  await deleteBillsForPatientIds(userId, patientIds);

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
