import { useRef, useState } from "react";
import { uploadClinicalDocument } from "../services/prescriptions";

const SYMPTOM_SUGGESTIONS = [
  "fever",
  "headache",
  "rash",
  "cough",
  "body ache",
  "chills",
  "nausea",
  "vomiting",
  "abdominal pain",
  "fatigue",
  "joint pain",
  "breathlessness",
];

const RESULT_OPTIONS = [
  "",
  "positive",
  "negative",
  "normal",
  "abnormal",
  "high",
  "low",
];

const emptySymptom = () => ({ name: "", duration: "", severity: "" });
const emptyTestResult = () => ({
  test_name: "",
  value: "",
  unit: "",
  result: "",
  reference_range: "",
});

export default function ClinicalContextForm({
  clinicalContext,
  onChange,
  onContinue,
  onBack,
  onDiagnosisExtracted,
  isUploading = false,
  error = "",
}) {
  const labInputRef = useRef(null);
  const dischargeInputRef = useRef(null);
  const [uploadError, setUploadError] = useState("");
  const [uploadingType, setUploadingType] = useState("");

  const symptoms = clinicalContext?.symptoms || [];
  const testResults = clinicalContext?.test_results || [];

  const updateSymptoms = (next) => {
    onChange({ ...clinicalContext, symptoms: next });
  };

  const updateTestResults = (next) => {
    onChange({ ...clinicalContext, test_results: next });
  };

  const addSymptomChip = (name) => {
    const normalized = name.trim().toLowerCase();
    if (!normalized) {
      return;
    }
    if (symptoms.some((item) => item.name?.toLowerCase() === normalized)) {
      return;
    }
    updateSymptoms([...symptoms, { name: normalized, duration: "", severity: "" }]);
  };

  const handleClinicalUpload = async (file, documentType) => {
    if (!file) {
      return;
    }
    setUploadError("");
    setUploadingType(documentType);
    try {
      const payload = await uploadClinicalDocument(file, documentType);
      const extracted = payload?.clinical_context || {};
      const mergedSymptoms = [...symptoms];
      for (const item of extracted.symptoms || []) {
        const name = String(item?.name || "").trim();
        if (!name) {
          continue;
        }
        if (!mergedSymptoms.some((s) => s.name?.toLowerCase() === name.toLowerCase())) {
          mergedSymptoms.push({
            name,
            duration: item.duration || "",
            severity: item.severity || "",
          });
        }
      }
      const mergedTests = [...testResults];
      for (const item of extracted.test_results || []) {
        const testName = String(item?.test_name || "").trim();
        if (!testName) {
          continue;
        }
        const existingIndex = mergedTests.findIndex(
          (entry) => entry.test_name?.toLowerCase() === testName.toLowerCase()
        );
        const normalized = {
          test_name: testName,
          value: item.value || "",
          unit: item.unit || "",
          result: item.result || "",
          reference_range: item.reference_range || "",
        };
        if (existingIndex >= 0) {
          mergedTests[existingIndex] = normalized;
        } else {
          mergedTests.push(normalized);
        }
      }
      onChange({
        ...clinicalContext,
        symptoms: mergedSymptoms,
        test_results: mergedTests,
        symptoms_source: extracted.symptoms?.length
          ? extracted.symptoms_source || clinicalContext?.symptoms_source
          : clinicalContext?.symptoms_source,
        test_results_source: extracted.test_results?.length
          ? extracted.test_results_source || clinicalContext?.test_results_source
          : clinicalContext?.test_results_source,
      });
      if (payload?.diagnosis && onDiagnosisExtracted) {
        onDiagnosisExtracted(String(payload.diagnosis).trim());
      }
    } catch (err) {
      setUploadError(err.message || "Could not extract clinical document.");
    } finally {
      setUploadingType("");
    }
  };

  return (
    <section className="bill-editor-shell clinical-context-shell">
      <header className="bill-editor-header">
        <div>
          <h2>Clinical context</h2>
          <p>
            Add symptoms and test results to check whether the diagnosis and
            treatment match Standard Treatment Guidelines.
          </p>
        </div>
      </header>

      <div className="clinical-section">
        <h3>Symptoms</h3>
        <div className="clinical-chip-row">
          {SYMPTOM_SUGGESTIONS.map((label) => (
            <button
              key={label}
              type="button"
              className="clinical-chip"
              onClick={() => addSymptomChip(label)}
            >
              {label}
            </button>
          ))}
        </div>
        <ul className="bill-editor-list">
          {symptoms.map((item, index) => (
            <li key={`symptom-${index}`} className="bill-editor-row">
              <div className="bill-editor-row-grid clinical-symptom-grid">
                <label className="bill-editor-field">
                  <span>Symptom</span>
                  <input
                    type="text"
                    value={item.name}
                    onChange={(event) => {
                      updateSymptoms(
                        symptoms.map((entry, entryIndex) =>
                          entryIndex === index
                            ? { ...entry, name: event.target.value }
                            : entry
                        )
                      );
                    }}
                  />
                </label>
                <label className="bill-editor-field">
                  <span>Duration (optional)</span>
                  <input
                    type="text"
                    value={item.duration || ""}
                    placeholder="e.g. 3 days"
                    onChange={(event) => {
                      updateSymptoms(
                        symptoms.map((entry, entryIndex) =>
                          entryIndex === index
                            ? { ...entry, duration: event.target.value }
                            : entry
                        )
                      );
                    }}
                  />
                </label>
                <button
                  type="button"
                  className="bill-editor-remove"
                  onClick={() =>
                    updateSymptoms(symptoms.filter((_, entryIndex) => entryIndex !== index))
                  }
                  aria-label={`Remove symptom ${index + 1}`}
                >
                  ×
                </button>
              </div>
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="bill-editor-add"
          onClick={() => updateSymptoms([...symptoms, emptySymptom()])}
        >
          + Add symptom
        </button>
      </div>

      <div className="clinical-section">
        <h3>Test results</h3>
        <ul className="bill-editor-list">
          {testResults.map((item, index) => (
            <li key={`test-${index}`} className="bill-editor-row">
              <div className="bill-editor-row-grid clinical-test-grid">
                <label className="bill-editor-field">
                  <span>Test</span>
                  <input
                    type="text"
                    value={item.test_name}
                    onChange={(event) => {
                      updateTestResults(
                        testResults.map((entry, entryIndex) =>
                          entryIndex === index
                            ? { ...entry, test_name: event.target.value }
                            : entry
                        )
                      );
                    }}
                  />
                </label>
                <label className="bill-editor-field">
                  <span>Value</span>
                  <input
                    type="text"
                    value={item.value || ""}
                    onChange={(event) => {
                      updateTestResults(
                        testResults.map((entry, entryIndex) =>
                          entryIndex === index
                            ? { ...entry, value: event.target.value }
                            : entry
                        )
                      );
                    }}
                  />
                </label>
                <label className="bill-editor-field">
                  <span>Unit</span>
                  <input
                    type="text"
                    value={item.unit || ""}
                    onChange={(event) => {
                      updateTestResults(
                        testResults.map((entry, entryIndex) =>
                          entryIndex === index
                            ? { ...entry, unit: event.target.value }
                            : entry
                        )
                      );
                    }}
                  />
                </label>
                <label className="bill-editor-field">
                  <span>Result</span>
                  <select
                    value={item.result || ""}
                    onChange={(event) => {
                      updateTestResults(
                        testResults.map((entry, entryIndex) =>
                          entryIndex === index
                            ? { ...entry, result: event.target.value }
                            : entry
                        )
                      );
                    }}
                  >
                    {RESULT_OPTIONS.map((option) => (
                      <option key={option || "unset"} value={option}>
                        {option || "—"}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="bill-editor-remove"
                  onClick={() =>
                    updateTestResults(
                      testResults.filter((_, entryIndex) => entryIndex !== index)
                    )
                  }
                  aria-label={`Remove test ${index + 1}`}
                >
                  ×
                </button>
              </div>
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="bill-editor-add"
          onClick={() => updateTestResults([...testResults, emptyTestResult()])}
        >
          + Add test result
        </button>
      </div>

      <div className="clinical-section">
        <h3>Optional documents</h3>
        <p className="comparison-settings-hint">
          Upload a lab report or discharge summary to pre-fill test results and
          symptoms. You can edit everything before analysis.
        </p>
        <div className="clinical-upload-row">
          <button
            type="button"
            className="bill-editor-secondary"
            disabled={Boolean(uploadingType)}
            onClick={() => labInputRef.current?.click()}
          >
            {uploadingType === "lab_report" ? "Uploading lab report…" : "Upload lab report"}
          </button>
          <button
            type="button"
            className="bill-editor-secondary"
            disabled={Boolean(uploadingType)}
            onClick={() => dischargeInputRef.current?.click()}
          >
            {uploadingType === "discharge_summary"
              ? "Uploading discharge summary…"
              : "Upload discharge summary"}
          </button>
        </div>
        <input
          ref={labInputRef}
          className="hidden-input"
          type="file"
          accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
          onChange={(event) => {
            handleClinicalUpload(event.target.files?.[0], "lab_report");
            event.target.value = "";
          }}
        />
        <input
          ref={dischargeInputRef}
          className="hidden-input"
          type="file"
          accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
          onChange={(event) => {
            handleClinicalUpload(event.target.files?.[0], "discharge_summary");
            event.target.value = "";
          }}
        />
        {uploadError && <p className="error-text">{uploadError}</p>}
      </div>

      <div className="bill-editor-actions">
        {onBack && (
          <button type="button" className="bill-editor-secondary" onClick={onBack}>
            Back
          </button>
        )}
        <button
          type="button"
          className="analyze-btn bill-editor-primary"
          disabled={isUploading}
          onClick={onContinue}
        >
          Continue
        </button>
      </div>
      {error && <p className="error-text">{error}</p>}
    </section>
  );
}
