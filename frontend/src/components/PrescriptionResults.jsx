import TreatmentAuditSection from "./TreatmentAuditSection";
import ClinicalHistoryUsedPanel from "./ClinicalHistoryUsedPanel";
import PatientQuestionsSection from "./PatientQuestionsSection";
import RestrictedMedicinesSection from "./RestrictedMedicinesSection";
import ReportActions from "./ReportActions";

export default function PrescriptionResults({ result, toolbar = null }) {
  if (
    !result?.treatment_audit_flags &&
    !result?.restricted_medicine_flags &&
    !(result?.patient_questions || []).length
  ) {
    return null;
  }

  const diagnosis =
    result.diagnosis || result.prescription?.diagnosis || "";
  const diagnosisUserProvided =
    result.diagnosis_user_provided ??
    result.prescription?.diagnosis_user_provided ??
    false;
  const medicines = result.prescription?.medicines || result.medicines || [];
  const tests = result.prescription?.tests || result.tests || [];
  const procedures = result.prescription?.procedures || result.procedures || [];

  return (
    <>
      {toolbar}

      <section className="prescription-summary-card">
        <h2>Prescription review</h2>
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

      <ReportActions report={result} />
    </>
  );
}
