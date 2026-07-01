import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import ClinicalHistoryFields from "./ClinicalHistoryFields";
import PatientHistoricalDocuments from "./PatientHistoricalDocuments";
import MedicalHistoryExportPanel from "./MedicalHistoryExportPanel";
import { patientToFormFields } from "./PatientForm";
import { getPatient, updatePatient } from "../services/patients";
import { emptyClinicalHistory } from "../utils/clinicalHistory";

export default function PatientMedicalHistorySection({
  userId,
  patient,
  documents = [],
  onDocumentsChange,
  onPatientUpdated,
  documentsEnabled = false,
  accountHistoryAllowed = false,
  accountConsent = null,
  disabled = false,
}) {
  const [history, setHistory] = useState(emptyClinicalHistory());
  const [savingHistory, setSavingHistory] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [historyInfo, setHistoryInfo] = useState("");

  useEffect(() => {
    if (!patient) {
      setHistory(emptyClinicalHistory());
      return;
    }
    setHistory(patientToFormFields(patient).clinicalHistory);
    setHistoryError("");
    setHistoryInfo("");
  }, [patient]);

  const handleSaveHistory = async () => {
    if (!userId || !patient?.id) {
      return;
    }
    setSavingHistory(true);
    setHistoryError("");
    setHistoryInfo("");
    try {
      const result = await updatePatient(userId, patient.id, {
        ...patientToFormFields(patient),
        clinicalHistory: history,
      });
      if (result.warning) {
        setHistoryInfo(result.warning);
      } else {
        setHistoryInfo("Medical history saved.");
      }
      const updated = await getPatient(userId, result.id);
      onPatientUpdated?.(updated);
    } catch (err) {
      setHistoryError(err.message || "Unable to save medical history.");
    } finally {
      setSavingHistory(false);
    }
  };

  if (!patient) {
    return null;
  }

  const historyDisabled = disabled || savingHistory;

  return (
    <section className="patient-medical-history-section">
      <ClinicalHistoryFields
        history={history}
        onChange={setHistory}
        disabled={historyDisabled}
      />

      <div className="patient-medical-history-actions">
        <button
          type="button"
          className="analyze-btn"
          onClick={handleSaveHistory}
          disabled={historyDisabled}
        >
          {savingHistory ? "Saving..." : "Save medical history"}
        </button>
      </div>

      {historyInfo && <p className="auth-info">{historyInfo}</p>}
      {historyError && <p className="error-text">{historyError}</p>}

      {documentsEnabled ? (
        <PatientHistoricalDocuments
          embedded
          userId={userId}
          patientId={patient.id}
          documents={documents}
          onChange={onDocumentsChange}
          disabled={disabled}
        />
      ) : (
        <div className="patient-historical-docs patient-historical-docs-embedded">
          <h3>Historical documents</h3>
          <p className="clinical-history-hint">
            {!accountHistoryAllowed
              ? "Enable medical history in your account settings to upload historical documents."
              : !patient?.savePastBills
              ? "Enable saving past bills for this patient in their profile to upload historical documents."
              : "Historical document upload is not available for this patient."}
          </p>
          {!accountHistoryAllowed && (
            <Link to="/consent/medical-history" className="patients-manage-link">
              Manage medical history consent
            </Link>
          )}
        </div>
      )}

      <MedicalHistoryExportPanel
        userId={userId}
        patient={patient}
        accountConsent={accountConsent}
        disabled={disabled || savingHistory}
      />
    </section>
  );
}
