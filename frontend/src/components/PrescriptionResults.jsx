import TreatmentAuditSection from "./TreatmentAuditSection";
import RestrictedMedicinesSection from "./RestrictedMedicinesSection";
import ReportActions from "./ReportActions";

export default function PrescriptionResults({ result, toolbar = null }) {
  if (!result?.treatment_audit_flags && !result?.restricted_medicine_flags) {
    return null;
  }

  const medicines = result.prescription?.medicines || result.medicines || [];
  const tests = result.prescription?.tests || result.tests || [];
  const procedures = result.prescription?.procedures || result.procedures || [];

  return (
    <>
      {toolbar}

      <section className="prescription-summary-card">
        <h2>Prescription review</h2>
        {result.diagnosis && (
          <p className="comparison-context">
            Diagnosis: <strong>{result.diagnosis}</strong>
            {result.diagnosis_user_provided ? " (provided by you)" : ""}
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

      <TreatmentAuditSection treatmentAuditFlags={result.treatment_audit_flags} />

      <RestrictedMedicinesSection
        restrictedMedicineFlags={result?.restricted_medicine_flags}
      />

      <ReportActions report={result} />
    </>
  );
}
