import { useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { updateReportAnnotations } from "../services/bills";
import {
  buildClinicianShareText,
  shareClinicianSummary,
} from "../utils/clinicianShare";
import {
  collectAllFlags,
  getFlagAnnotation,
  normalizeClinicianAnnotations,
  setFlagAnnotation,
  setGeneralAnnotationNote,
} from "../utils/reportAnnotations";

export default function ClinicianSharePanel({ report, onReportUpdate }) {
  const { user } = useAuth();
  const reportId = report?.firestoreId || report?.id || report?.localId || null;
  const [annotations, setAnnotations] = useState(() =>
    normalizeClinicianAnnotations(report?.clinician_annotations)
  );
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [messageTone, setMessageTone] = useState("info");

  const flags = useMemo(() => collectAllFlags(report), [report]);

  const applyAnnotations = (next) => {
    setAnnotations(next);
    onReportUpdate?.({
      ...report,
      clinician_annotations: next,
      annotations_updated_at: next.updated_at,
    });
  };

  const handleSave = async () => {
    if (!user?.uid || !reportId) {
      setMessage("Save the report to your account before storing notes.");
      setMessageTone("error");
      return;
    }
    setBusy("save");
    setMessage("");
    try {
      const saved = await updateReportAnnotations(user.uid, reportId, annotations);
      applyAnnotations(saved.clinician_annotations);
      setMessage("Notes saved.");
      setMessageTone("info");
    } catch (error) {
      setMessage(error.message || "Could not save notes.");
      setMessageTone("error");
    } finally {
      setBusy("");
    }
  };

  const handleShare = async () => {
    setBusy("share");
    setMessage("");
    try {
      const outcome = await shareClinicianSummary(report, annotations);
      if (outcome.cancelled) {
        return;
      }
      if (outcome.shared && outcome.method === "clipboard") {
        setMessage("Clinician summary copied to clipboard.");
        setMessageTone("info");
        return;
      }
      if (outcome.shared) {
        setMessage("Shared with your chosen app.");
        setMessageTone("info");
        return;
      }
      setMessage("Sharing is not supported here. Use Save notes, then copy from preview.");
      setMessageTone("error");
    } catch (error) {
      setMessage(error.message || "Could not share the summary.");
      setMessageTone("error");
    } finally {
      setBusy("");
    }
  };

  const previewText = buildClinicianShareText(report, annotations);

  return (
    <section className="clinician-share-panel">
      <header className="clinician-share-header">
        <div>
          <h3>Share with your doctor</h3>
          <p>
            Add notes for your clinician, then share a plain-language summary of
            findings and questions.
          </p>
        </div>
      </header>

      <label className="setting-field setting-field-full">
        <span>General note for your doctor (optional)</span>
        <textarea
          rows={3}
          value={annotations.general_note}
          placeholder="Example: I want to understand whether the repeat CBC was necessary."
          onChange={(event) =>
            applyAnnotations(setGeneralAnnotationNote(annotations, event.target.value))
          }
        />
      </label>

      {flags.length > 0 && (
        <div className="clinician-flag-notes">
          <h4>Notes on specific findings</h4>
          {flags.map((flag, index) => (
            <label key={`${flag.type}-${flag.item}-${index}`} className="setting-field setting-field-full">
              <span>{flag.item || flag.display_label || "Finding"}</span>
              <textarea
                rows={2}
                value={getFlagAnnotation(annotations, flag, index)}
                placeholder="Add a note or question for your doctor about this finding."
                onChange={(event) =>
                  applyAnnotations(
                    setFlagAnnotation(annotations, flag, index, event.target.value)
                  )
                }
              />
            </label>
          ))}
        </div>
      )}

      <details className="clinician-share-preview">
        <summary>Preview clinician summary</summary>
        <pre>{previewText}</pre>
      </details>

      <div className="bill-editor-actions clinician-share-actions">
        <button
          type="button"
          className="bill-editor-secondary"
          onClick={handleSave}
          disabled={Boolean(busy)}
        >
          {busy === "save" ? "Saving…" : "Save notes"}
        </button>
        <button
          type="button"
          className="analyze-btn bill-editor-primary"
          onClick={handleShare}
          disabled={Boolean(busy)}
        >
          {busy === "share" ? "Sharing…" : "Share with doctor"}
        </button>
      </div>

      {message && (
        <p className={messageTone === "info" ? "auth-info" : "error-text"}>{message}</p>
      )}
    </section>
  );
}
