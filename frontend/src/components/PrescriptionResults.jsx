import TreatmentAuditSection from "./TreatmentAuditSection";
import ClinicalHistoryUsedPanel from "./ClinicalHistoryUsedPanel";
import CombinedNarrative from "./CombinedNarrative";
import PatientQuestionsSection from "./PatientQuestionsSection";
import RestrictedMedicinesSection from "./RestrictedMedicinesSection";
import ReportActions from "./ReportActions";
import ClinicianSharePanel from "./ClinicianSharePanel";

function hasDisplayablePrescriptionContent(result) {
  if (!result) {
    return false;
  }
  if (result.report_kind === "clinical" || result.report_kind === "prescription") {
    return true;
  }
  const clinical = result.clinical_context || {};
  return Boolean(
    result.treatment_audit_flags ||
      result.restricted_medicine_flags?.length ||
      (result.patient_questions || []).length ||
      result.treatment_audit_flags?.patient_questions?.length ||
      result.action_plan?.combined_narrative ||
      clinical.symptoms?.length ||
      clinical.test_results?.length ||
      result.diagnosis ||
      result.prescription?.diagnosis ||
      result.prescription?.medicines?.length ||
      result.medicines?.length ||
      result.prescription?.tests?.length ||
      result.tests?.length ||
      result.prescription?.procedures?.length ||
      result.procedures?.length
  );
}

export default function PrescriptionResults({ result, toolbar = null, onReportUpdate }) {
  if (!hasDisplayablePrescriptionContent(result)) {
    return (
      <>
        {toolbar}
        <p className="auth-info">No review findings are available for this report yet.</p>
      </>
    );
  }

  const isClinicalReview = result.report_kind === "clinical";
  const diagnosis =
    result.diagnosis || result.prescription?.diagnosis || "";
  const diagnosisUserProvided =
    result.diagnosis_user_provided ??
    result.prescription?.diagnosis_user_provided ??
    false;
  const medicines = result.prescription?.medicines || result.medicines || [];
  const tests = result.prescription?.tests || result.tests || [];
  const procedures = result.prescription?.procedures || result.procedures || [];
  const symptoms = result.clinical_context?.symptoms || [];
  const testResults = result.clinical_context?.test_results || [];

  return (
    <>
      {toolbar}

      <section className="prescription-summary-card">
        <h2>{isClinicalReview ? "Clinical review" : "Prescription review"}</h2>
        {diagnosis && (
          <p className="comparison-context">
            Diagnosis: <strong>{diagnosis}</strong>
            {diagnosisUserProvided ? " (provided by you)" : ""}
          </p>
        )}
        {result.prescription?.prescriber && (
          <p className="comparison-context">
            Prescriber: <strong>{result.prescription.prescriber}</strong>
          </p>
        )}

        {isClinicalReview && symptoms.length > 0 && (
          <div className="prescription-item-group">
            <h3>Symptoms reviewed</h3>
            <ul>
              {symptoms.map((item, index) => (
                <li key={`symptom-${index}`}>
                  <strong>{item.name}</strong>
                  {[item.duration, item.severity].filter(Boolean).join(" · ")}
                </li>
              ))}
            </ul>
          </div>
        )}

        {isClinicalReview && testResults.length > 0 && (
          <div className="prescription-item-group">
            <h3>Test results reviewed</h3>
            <ul>
              {testResults.map((item, index) => (
                <li key={`lab-${index}`}>
                  <strong>{item.test_name}</strong>
                  {[item.value, item.unit, item.result, item.reference_range ? `ref ${item.reference_range}` : ""]
                    .filter(Boolean)
                    .join(" · ")}
                </li>
              ))}
            </ul>
          </div>
        )}

        {medicines.length > 0 && (
          <div className="prescription-item-group">
            <h3>Medicines</h3>
            <ul>
              {medicines.map((item, index) => (
                <li key={`med-${index}`}>
                  <strong>{item.name}</strong>
                  {[item.dose, item.frequency, item.duration]
                    .filter(Boolean)
                    .join(" · ")}
                </li>
              ))}
            </ul>
          </div>
        )}

        {tests.length > 0 && (
          <div className="prescription-item-group">
            <h3>Tests</h3>
            <ul>
              {tests.map((item, index) => (
                <li key={`test-${index}`}>{item.name}</li>
              ))}
            </ul>
          </div>
        )}

        {procedures.length > 0 && (
          <div className="prescription-item-group">
            <h3>Procedures</h3>
            <ul>
              {procedures.map((item, index) => (
                <li key={`proc-${index}`}>{item.name}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <PatientQuestionsSection report={result} />
      <CombinedNarrative narrative={result?.action_plan?.combined_narrative} />

      <TreatmentAuditSection
        treatmentAuditFlags={result.treatment_audit_flags}
        report={result}
      />

      <ClinicalHistoryUsedPanel
        clinicalHistoryUsed={
          result?.clinical_history_used ||
          result?.treatment_audit_flags?.clinical_history_used
        }
        patientId={result?.patient?.id}
      />

      <RestrictedMedicinesSection
        restrictedMedicineFlags={result?.restricted_medicine_flags}
      />

      <ClinicianSharePanel report={result} onReportUpdate={onReportUpdate} />

      <ReportActions report={result} />
    </>
  );
}
