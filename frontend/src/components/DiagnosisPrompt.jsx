import { useEffect, useMemo, useState } from "react";
import { fetchStgConditions } from "../services/prescriptions";

const COMMON_SUGGESTIONS = [
  "Malaria",
  "Dengue",
  "Typhoid or Enteric Fever",
  "Acute Fever",
  "Urinary Tract Infections (UTIs)",
  "Pneumonia",
  "Hypertension",
  "Diabetes Mellitus",
];

export default function DiagnosisPrompt({
  initialDiagnosis = "",
  onSubmit,
  onCancel = null,
  error = "",
}) {
  const [diagnosis, setDiagnosis] = useState(initialDiagnosis);
  const [conditions, setConditions] = useState([]);

  useEffect(() => {
    let cancelled = false;
    fetchStgConditions()
      .then((list) => {
        if (!cancelled) {
          setConditions(list);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setConditions([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const suggestions = useMemo(() => {
    const merged = [...COMMON_SUGGESTIONS];
    for (const name of conditions.slice(0, 300)) {
      if (!merged.some((item) => item.toLowerCase() === name.toLowerCase())) {
        merged.push(name);
      }
    }
    const query = diagnosis.trim().toLowerCase();
    if (!query) {
      return merged.slice(0, 12);
    }
    return merged
      .filter((name) => name.toLowerCase().includes(query))
      .slice(0, 12);
  }, [conditions, diagnosis]);

  const handleSubmit = (event) => {
    event.preventDefault();
    const value = diagnosis.trim();
    if (!value) {
      return;
    }
    onSubmit(value);
  };

  return (
    <section className="upload-card diagnosis-prompt-card">
      <p className="comparison-settings-title">Diagnosis required</p>
      <p className="comparison-settings-hint">
        The prescription did not include a clear diagnosis. Enter the condition
        so we can check tests and medicines against Standard Treatment
        Guidelines.
      </p>
      <form onSubmit={handleSubmit}>
        <label className="setting-field setting-field-full">
          <span>Diagnosis / condition</span>
          <input
            type="text"
            value={diagnosis}
            onChange={(event) => setDiagnosis(event.target.value)}
            placeholder="e.g. Malaria, Dengue, UTI"
            autoFocus
          />
        </label>
        {suggestions.length > 0 && (
          <div className="diagnosis-suggestions">
            {suggestions.map((name) => (
              <button
                key={name}
                type="button"
                className="diagnosis-suggestion-chip"
                onClick={() => setDiagnosis(name)}
              >
                {name}
              </button>
            ))}
          </div>
        )}
        <div className="bill-editor-actions">
          {onCancel && (
            <button
              type="button"
              className="bill-editor-secondary"
              onClick={onCancel}
            >
              Back
            </button>
          )}
          <button type="submit" className="analyze-btn" disabled={!diagnosis.trim()}>
            Continue
          </button>
        </div>
      </form>
      {error && <p className="error-text">{error}</p>}
    </section>
  );
}
