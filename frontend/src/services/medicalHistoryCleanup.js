import { clearSecureKeysMatching } from "./secureLocalStore";
import { deleteAllUserBills } from "./bills";
import { deleteAllHistoricalDocumentsForUser } from "./patientHistoricalDocuments";
import { getPatients } from "./patients";

/**
 * Permanently delete all saved medical history for a user (cloud + local).
 * Called when medical-history consent is revoked.
 */
export async function deleteAllMedicalHistoryForUser(userId) {
  if (!userId) {
    return;
  }

  let patientIds = [];
  try {
    const patients = await getPatients(userId);
    patientIds = [
      ...new Set(
        (patients || [])
          .map((entry) => entry.firestoreId || entry.id || entry.localId)
          .filter(Boolean)
      ),
    ];
  } catch (error) {
    console.warn("Could not list patients while deleting medical history:", error);
  }

  await Promise.all([
    deleteAllUserBills(userId),
    deleteAllHistoricalDocumentsForUser(userId, patientIds),
  ]);

  clearSecureKeysMatching("swaasth_question_responses_");
}
