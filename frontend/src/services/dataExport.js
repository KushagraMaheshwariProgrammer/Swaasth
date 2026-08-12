import { doc, getDoc, serverTimestamp, setDoc } from "firebase/firestore";
import { awaitFirestoreReady, db } from "../firebase";
import { getUserBills } from "./bills";
import { getPatients } from "./patients";
import { getPatientHospitals } from "./patientHospitals";
import { getPatientHistoricalDocuments } from "./patientHistoricalDocuments";
import { getUserProfileData } from "./userProfile";

function serializeValue(value) {
  if (value == null) {
    return value;
  }
  if (typeof value?.toDate === "function") {
    return value.toDate().toISOString();
  }
  if (Array.isArray(value)) {
    return value.map(serializeValue);
  }
  if (typeof value === "object") {
    const out = {};
    for (const [key, item] of Object.entries(value)) {
      out[key] = serializeValue(item);
    }
    return out;
  }
  return value;
}

export async function exportUserData(userId) {
  if (!userId) {
    throw new Error("Missing user id.");
  }

  const profile = await getUserProfileData(userId);
  const patients = await getPatients(userId);
  const bills = await getUserBills(userId);

  const hospitals = {};
  const historicalDocuments = {};
  for (const patient of patients || []) {
    const patientId = patient.firestoreId || patient.id;
    if (!patientId) {
      continue;
    }
    try {
      hospitals[patientId] = await getPatientHospitals(userId, patientId);
    } catch (error) {
      hospitals[patientId] = { error: error?.message || "Could not load hospitals." };
    }
    try {
      historicalDocuments[patientId] = await getPatientHistoricalDocuments(
        userId,
        patientId
      );
    } catch (error) {
      historicalDocuments[patientId] = {
        error: error?.message || "Could not load historical documents.",
      };
    }
  }

  return serializeValue({
    exportedAt: new Date().toISOString(),
    userId,
    profile: profile || {},
    patients,
    hospitals,
    historicalDocuments,
    bills,
  });
}

export function downloadJsonFile(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function recordDeletionRequest(userId, email) {
  if (!userId) {
    return;
  }
  try {
    await awaitFirestoreReady();
    await setDoc(doc(db, "deletionRequests", userId), {
      userId,
      email: email || "",
      requestedAt: serverTimestamp(),
      status: "started",
      note: "In-app account deletion started.",
    });
  } catch (error) {
    console.warn("Could not record deletion request:", error);
  }
}

export async function markDeletionRequestDataDeleted(userId) {
  if (!userId) {
    return;
  }
  try {
    await awaitFirestoreReady();
    const ref = doc(db, "deletionRequests", userId);
    const snapshot = await getDoc(ref);
    if (!snapshot.exists()) {
      return;
    }
    await setDoc(
      ref,
      {
        status: "data_deleted",
        note: "Firestore and local data deleted; Auth deletion follows.",
      },
      { merge: true }
    );
  } catch (error) {
    console.warn("Could not update deletion request:", error);
  }
}
