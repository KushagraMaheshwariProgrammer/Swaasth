import { useRef, useState } from "react";

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
  continueLabel = "Continue",
}) {
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

  return (
    <section className="bill-editor-shell clinical-context-shell">
      <header className="bill-editor-header">
        <div>
          <h2>Clinical context</h2>
          <p>
            Review symptoms and test results extracted from your documents, or add
            them manually to check whether diagnosis and treatment match Standard
            Treatment Guidelines.
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
          {continueLabel}
        </button>
      </div>
      {error && <p className="error-text">{error}</p>}
    </section>
  );
}
