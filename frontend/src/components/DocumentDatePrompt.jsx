import { useEffect, useState } from "react";
import { documentTypeLabel } from "../utils/documentBundle";
import {
  applyConfirmedDates,
  itemsMissingDates,
  normalizeToIsoDate,
} from "../utils/documentDates";

export default function DocumentDatePrompt({
  items = [],
  title = "Confirm document dates",
  description = "We could not read a date on some documents. Enter the date each document relates to so your medical history stays in order.",
  confirmLabel = "Continue",
  onConfirm,
  onCancel,
}) {
  const [draftItems, setDraftItems] = useState(() => applyConfirmedDates(items));
  const [error, setError] = useState("");

  useEffect(() => {
    setDraftItems(applyConfirmedDates(items));
    setError("");
  }, [items]);

  const missing = itemsMissingDates(draftItems);

  const updateDate = (id, value) => {
    setDraftItems((current) =>
      current.map((item) =>
        item.id === id ? { ...item, documentDate: value } : item
      )
    );
    setError("");
  };

  const handleConfirm = () => {
    const normalized = applyConfirmedDates(draftItems);
    if (itemsMissingDates(normalized).length) {
      setError("Enter a date for every document before continuing.");
      return;
    }
    onConfirm?.(normalized);
  };

  if (!draftItems.length) {
    return null;
  }

  return (
    <div className="document-date-prompt-overlay" role="dialog" aria-modal="true">
      <div className="document-date-prompt-card">
        <h2>{title}</h2>
        <p className="clinical-history-hint">{description}</p>

        <ul className="document-date-prompt-list">
          {draftItems.map((item) => {
            const detected = normalizeToIsoDate(item.detectedDate);
            const needsInput = !detected;
            return (
              <li key={item.id} className="document-date-prompt-item">
                <div>
                  <strong>{item.filename}</strong>
                  <p>{documentTypeLabel(item.documentType)}</p>
                  {detected && !needsInput ? (
                    <p className="auth-info">Detected date: {detected}</p>
                  ) : (
                    <p className="clinical-history-hint">
                      Date not detected — please enter it below.
                    </p>
                  )}
                </div>
                <label className="setting-field">
                  <span>Document date</span>
                  <input
                    type="date"
                    value={normalizeToIsoDate(item.documentDate)}
                    onChange={(event) => updateDate(item.id, event.target.value)}
                    required
                  />
                </label>
              </li>
            );
          })}
        </ul>

        {missing.length > 0 && (
          <p className="clinical-history-hint">
            {missing.length} document{missing.length === 1 ? "" : "s"} still need
            a date.
          </p>
        )}
        {error && <p className="error-text">{error}</p>}

        <div className="document-date-prompt-actions">
          {onCancel && (
            <button
              type="button"
              className="bill-editor-secondary"
              onClick={onCancel}
            >
              Cancel
            </button>
          )}
          <button type="button" className="analyze-btn" onClick={handleConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
