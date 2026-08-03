import { useCallback, useEffect, useRef, useState } from "react";
import {
  TERMS_LAST_UPDATED,
  TERMS_SECTIONS,
} from "../data/termsAndConditions";
import {
  PRIVACY_POLICY_LAST_UPDATED,
  PRIVACY_POLICY_SECTIONS,
} from "../data/privacyPolicy";
import { hasScrolledToBottom as checkScrolledToBottom } from "../utils/termsScroll";

export default function TermsAndConditionsModal({
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
      aria-labelledby="terms-modal-title"
    >
      <div className="modal-panel terms-modal">
        <header className="modal-header">
          <div>
            <h2 id="terms-modal-title">Terms and Privacy Policy</h2>
            <p className="terms-modal-updated">
              Terms last updated: {TERMS_LAST_UPDATED} · Privacy Policy last
              updated: {PRIVACY_POLICY_LAST_UPDATED}
            </p>
          </div>
        </header>

        <div
          ref={bodyRef}
          className="modal-body terms-modal-body"
          tabIndex={0}
          aria-label="Terms and conditions document"
        >
          <p className="terms-modal-lead">
            Please read the full Terms and Conditions and Privacy Policy below.
            You must scroll to the end and confirm your agreement before using
            Swaasth.
          </p>

          <h2 className="terms-modal-doc-title">Terms and Conditions</h2>

          {TERMS_SECTIONS.map((section) => (
            <section key={`terms-${section.title}`} className="terms-section">
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

          <h2 className="terms-modal-doc-title">Privacy Policy</h2>

          {PRIVACY_POLICY_SECTIONS.map((section) => (
            <section key={`privacy-${section.title}`} className="terms-section">
              <h3>{section.title}</h3>
              {section.paragraphs.map((paragraph, index) => (
                <p key={`privacy-${section.title}-p-${index}`}>{paragraph}</p>
              ))}
              {section.bullets.length > 0 && (
                <ul>
                  {section.bullets.map((item, index) => (
                    <li key={`privacy-${section.title}-b-${index}`}>{item}</li>
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
              I have read and agree to the Terms and Conditions and Privacy
              Policy of Swaasth.
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
              Decline
            </button>
            <button
              type="button"
              className="analyze-btn"
              onClick={onAccept}
              disabled={!canAccept}
            >
              {isSubmitting ? "Saving..." : "Accept and continue"}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
