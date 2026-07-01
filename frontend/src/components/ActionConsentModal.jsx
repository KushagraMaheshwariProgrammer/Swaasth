import { useCallback, useEffect, useRef, useState } from "react";
import { ACTION_CONSENT_SECTIONS } from "../data/actionConsent";
import { hasScrolledToBottom as checkScrolledToBottom } from "../utils/termsScroll";

export default function ActionConsentModal({ onAccept, onDecline }) {
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

  const canAccept = hasScrolledToBottom && agreed;

  return (
    <div
      className="modal-overlay terms-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="action-consent-modal-title"
    >
      <div className="modal-panel terms-modal">
        <header className="modal-header">
          <div>
            <h2 id="action-consent-modal-title">Take action / Dispute — consent</h2>
            <p className="terms-modal-updated">
              Please read before continuing
            </p>
          </div>
        </header>

        <div
          ref={bodyRef}
          className="modal-body terms-modal-body"
          tabIndex={0}
          aria-label="Take action consent document"
        >
          <p className="terms-modal-lead">
            Before using Take action / Dispute, you must read the notice below,
            scroll to the end, and confirm that you understand and accept it.
            The app creators are not legally responsible for any outcomes from
            actions you take.
          </p>

          {ACTION_CONSENT_SECTIONS.map((section) => (
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
              disabled={!hasScrolledToBottom}
              onChange={(event) => setAgreed(event.target.checked)}
            />
            <span>
              I understand that Swaasth provides informational assistance only,
              that I act on my own responsibility, and that the app creators are
              not liable for any outcomes from actions I take.
            </span>
          </label>

          <div className="terms-modal-actions">
            <button
              type="button"
              className="bill-editor-secondary"
              onClick={onDecline}
            >
              Decline
            </button>
            <button
              type="button"
              className="analyze-btn"
              onClick={onAccept}
              disabled={!canAccept}
            >
              Accept and continue
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
