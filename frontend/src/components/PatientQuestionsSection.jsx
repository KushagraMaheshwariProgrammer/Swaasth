import { useEffect, useState } from "react";
import { collectPatientQuestions, getAuditConfidenceMeta } from "../auditAdvocacyUtils";
import { getSecureJson, setSecureJson } from "../services/secureLocalStore";

const STORAGE_PREFIX = "swaasth_question_responses_";

function reportStorageKey(report) {
  const id =
    report?.id ||
    report?.filename ||
    report?.diagnosis ||
    report?.patient?.id ||
    "report";
  return `${STORAGE_PREFIX}${id}`;
}

export default function PatientQuestionsSection({
  report,
  showResponseLog = true,
  title = "Questions to ask before you pay or discharge",
}) {
  const questions = collectPatientQuestions(report);
  const [responses, setResponses] = useState({});

  useEffect(() => {
    if (!report || !showResponseLog) {
      return;
    }
    try {
      const saved = getSecureJson(reportStorageKey(report), null);
      if (saved && typeof saved === "object") {
        setResponses(saved);
      } else {
        setResponses({});
      }
    } catch {
      setResponses({});
    }
  }, [report, showResponseLog]);

  const saveResponse = (index, value) => {
    const next = { ...responses, [index]: value };
    setResponses(next);
    try {
      setSecureJson(reportStorageKey(report), next);
    } catch {
      // ignore storage errors
    }
  };

  if (!questions.length) {
    return null;
  }

  return (
    <section className="audit-section patient-questions-section">
      <div className="audit-section-header">
        <h3>{title}</h3>
        <span className="audit-flag-count">
          {questions.length} question{questions.length === 1 ? "" : "s"}
        </span>
      </div>
      <p className="comparison-settings-hint">
        These are suggested clarification questions based on government guidelines and
        billing patterns. They are not medical advice, diagnoses, or accusations against
        your hospital or doctor. Discuss clinical points with your doctor before changing
        any treatment, test, or medicine.
      </p>
      <ol className="patient-questions-list">
        {questions.map((entry, index) => {
          const meta = getAuditConfidenceMeta(entry.confidence);
          return (
            <li key={`pq-${index}`} className="patient-question-item">
              <div className="patient-question-top">
                <p className="patient-question-text">{entry.question}</p>
                <span className={meta.badgeClass}>{meta.label}</span>
              </div>
              {entry.item && (
                <p className="patient-question-item-ref">
                  About: <strong>{entry.item}</strong>
                  {entry.display_label ? ` · ${entry.display_label}` : ""}
                </p>
              )}
              {entry.guideline_basis && (
                <p className="patient-question-basis">{entry.guideline_basis}</p>
              )}
              <p className="patient-question-hint">{meta.hint}</p>
              {showResponseLog && (
                <label className="patient-question-response">
                  <span>Hospital response (optional)</span>
                  <textarea
                    rows={2}
                    value={responses[index] || ""}
                    onChange={(event) => saveResponse(index, event.target.value)}
                    placeholder="Record what the hospital or doctor said..."
                  />
                </label>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
