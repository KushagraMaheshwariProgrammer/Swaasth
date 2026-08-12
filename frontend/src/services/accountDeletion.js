import { deleteDoc, doc } from "firebase/firestore";
import { awaitFirestoreReady, db } from "../firebase";
import { clearSecureKeysMatching } from "./secureLocalStore";
import { deleteAllMedicalHistoryForUser } from "./medicalHistoryCleanup";
import { clearLocalMedicalHistoryConsent } from "./localMedicalHistoryConsentStore";
import { clearLocalTermsAcceptance } from "./localTermsStore";
import {
  clearLocalPatientsForUser,
  getLocalPatients,
} from "./localPatientStore";
import { clearLocalHospitalsForUser } from "./patientHospitals";
import { deletePatient, getPatients } from "./patients";

function userProfileRef(userId) {
  return doc(db, "users", userId);
}

function collectPatientIds(patients) {
  return [
    ...new Set(
      (patients || [])
        .map((entry) => entry.firestoreId || entry.id || entry.localId)
        .filter(Boolean)
    ),
  ];
}

/**
 * Permanently delete all Firestore and local data for a user.
 * Call before deleting the Firebase Auth account.
 */
export async function deleteAllUserData(userId) {
  if (!userId) {
    throw new Error("Missing user id.");
  }

  await deleteAllMedicalHistoryForUser(userId);

  let patients = [];
  try {
    patients = await getPatients(userId);
  } catch (error) {
    console.warn("Could not list cloud patients during account deletion:", error);
    patients = getLocalPatients(userId).map((entry) => ({
      id: entry.firestoreId || entry.localId,
      firestoreId: entry.firestoreId,
      localId: entry.localId,
    }));
  }

  const patientIds = collectPatientIds(patients);
  for (const patientId of patientIds) {
    try {
      await deletePatient(userId, patientId);
    } catch (error) {
      console.error(`Failed to delete patient ${patientId}:`, error);
    }
  }

  clearLocalPatientsForUser(userId);
  clearLocalHospitalsForUser(userId);
  clearLocalMedicalHistoryConsent(userId);
  clearLocalTermsAcceptance(userId);
  clearSecureKeysMatching("swaasth_question_responses_");

  try {
    await awaitFirestoreReady();
    await deleteDoc(userProfileRef(userId));
  } catch (error) {
    const code = error?.code || "";
    if (code !== "not-found") {
      console.error("Failed to delete user profile document:", error);
      throw error;
    }
  }
}
