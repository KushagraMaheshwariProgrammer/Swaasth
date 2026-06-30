import { useCallback, useEffect, useRef, useState } from "react";
import {
  MEDICAL_HISTORY_CONSENT_LAST_UPDATED,
  MEDICAL_HISTORY_CONSENT_SECTIONS,
} from "../data/medicalHistoryConsent";
import { hasScrolledToBottom as checkScrolledToBottom } from "../utils/termsScroll";

export default function MedicalHistoryConsentModal({
  onAccept,
  onDecline,
  isSubmitting = false,
  error = "",
}) {
  const bodyRef = useRef(null);
  const [hasScrolledToBottom, setHasScrolledToBottom] = useState(false);
  const [agreed, setAgreed] = useState(false);

  const updateScrollState = useCallback(() => {
    setHasScrolledToBottom(checkScrolledToBottom(bodyRef.current));
  }, []);

  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, []);

  useEffect(() => {
    updateScrollState();
    const element = bodyRef.current;
    if (!element) {
      return undefined;
    }

    element.addEventListener("scroll", updateScrollState, { passive: true });
    window.addEventListener("resize", updateScrollState);

    let resizeObserver;
    if (typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(updateScrollState);
      resizeObserver.observe(element);
    }

    return () => {
      element.removeEventListener("scroll", updateScrollState);
      window.removeEventListener("resize", updateScrollState);
      resizeObserver?.disconnect();
    };
  }, [updateScrollState]);

  const canAccept = hasScrolledToBottom && agreed && !isSubmitting;

  return (
    <div
      className="modal-overlay terms-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="medical-history-consent-title"
    >
      <div className="modal-panel terms-modal">
        <header className="modal-header">
          <div>
            <h2 id="medical-history-consent-title">Medical history consent</h2>
            <p className="terms-modal-updated">
              Last updated: {MEDICAL_HISTORY_CONSENT_LAST_UPDATED}
            </p>
          </div>
        </header>

        <div
          ref={bodyRef}
          className="modal-body terms-modal-body"
          tabIndex={0}
          aria-label="Medical history consent document"
        >
          <p className="terms-modal-lead">
            Saving medical history is optional. You can use Swaasth to analyze
            documents without saving reports. Read the details below and choose
            whether to enable history for your account.
          </p>

          {MEDICAL_HISTORY_CONSENT_SECTIONS.map((section) => (
            <section key={section.title} className="terms-section">
              <h3>{section.title}</h3>
              {section.paragraphs.map((paragraph, index) => (
                <p key={`${section.title}-p-${index}`}>{paragraph}</p>
              ))}
              {section.bullets.length > 0 && (
                <ul>
                  {section.bullets.map((item, index) => (
                    <li key={`${section.title}-b-${index}`}>{item}</li>
                  ))}
                </ul>
              )}
            </section>
          ))}

          <div className="terms-scroll-end" aria-hidden="true" />
        </div>

        <footer className="modal-footer terms-modal-footer">
          {!hasScrolledToBottom && (
            <p className="terms-scroll-hint">
              Scroll to the bottom of the document to enable acceptance.
            </p>
          )}

          <label
            className={`terms-checkbox-label ${
              hasScrolledToBottom ? "" : "terms-checkbox-label-disabled"
            }`}
          >
            <input
              type="checkbox"
              checked={agreed}
              disabled={!hasScrolledToBottom || isSubmitting}
              onChange={(event) => setAgreed(event.target.checked)}
            />
            <span>
              I consent to saving medical history (analysis reports) to my
              Swaasth account.
            </span>
          </label>

          {error && <p className="error-text">{error}</p>}

          <div className="terms-modal-actions">
            <button
              type="button"
              className="bill-editor-secondary"
              onClick={onDecline}
              disabled={isSubmitting}
            >
              Continue without saving history
            </button>
            <button
              type="button"
              className="analyze-btn"
              onClick={onAccept}
              disabled={!canAccept}
            >
              {isSubmitting ? "Saving..." : "Enable medical history"}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
