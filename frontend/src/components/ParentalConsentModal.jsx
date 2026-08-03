import { useCallback, useEffect, useRef, useState } from "react";
import {
  GUARDIAN_RELATIONSHIP_OPTIONS,
  PARENTAL_CONSENT_LAST_UPDATED,
  PARENTAL_CONSENT_SECTIONS,
  parentalConsentDeclaration,
} from "../data/parentalConsent";
import { buildParentalConsentRecord } from "../utils/parentalConsent";
import {
  getAccountErrorMessage,
  reauthenticateCurrentUser,
  usesPasswordProvider,
} from "../auth/accountSecurity";
import { useAuth } from "../context/AuthContext";
import { hasScrolledToBottom as checkScrolledToBottom } from "../utils/termsScroll";

export default function ParentalConsentModal({
  childName,
  onConsent,
  onCancel,
}) {
  const { user } = useAuth();
  const passwordProvider = usesPasswordProvider(user);
  const bodyRef = useRef(null);
  const [hasScrolledToBottom, setHasScrolledToBottom] = useState(false);
  const [guardianName, setGuardianName] = useState(user?.displayName || "");
  const [relationship, setRelationship] = useState("");
  const [password, setPassword] = useState("");
  const [declared, setDeclared] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState("");

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

  const detailsComplete =
    guardianName.trim().length > 0 &&
    relationship !== "" &&
    (!passwordProvider || password.length > 0);
  const canConfirm =
    hasScrolledToBottom && declared && detailsComplete && !verifying;

  const handleConfirm = async () => {
    if (!canConfirm) {
      return;
    }
    setVerifying(true);
    setError("");
    try {
      await reauthenticateCurrentUser(passwordProvider ? password : undefined);
      const record = buildParentalConsentRecord({
        guardianName,
        relationship,
        guardianUid: user.uid,
        guardianEmail: user.email || "",
        verificationMethod: passwordProvider
          ? "password_reauth"
          : "google_reauth",
      });
      if (!record) {
        throw new Error("Could not record consent. Please try again.");
      }
      await onConsent(record);
    } catch (err) {
      setError(getAccountErrorMessage(err));
      setVerifying(false);
    }
  };

  return (
    <div
      className="modal-overlay terms-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="parental-consent-title"
    >
      <div className="modal-panel terms-modal">
        <header className="modal-header">
          <div>
            <h2 id="parental-consent-title">Parental consent required</h2>
            <p className="terms-modal-updated">
              Last updated: {PARENTAL_CONSENT_LAST_UPDATED}
            </p>
          </div>
        </header>

        <div
          ref={bodyRef}
          className="modal-body terms-modal-body"
          tabIndex={0}
          aria-label="Parental consent document"
        >
          <p className="terms-modal-lead">
            {childName?.trim() ? `"${childName.trim()}"` : "This patient"} is
            below 18 years of age. Indian law requires verifiable consent from a
            parent or lawful guardian before Swaasth can process this child&apos;s
            data.
          </p>

          {PARENTAL_CONSENT_SECTIONS.map((section) => (
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
              Scroll to the bottom of the document to continue.
            </p>
          )}

          <div className="comparison-settings-grid">
            <label className="setting-field">
              <span>Your full name (parent/guardian)</span>
              <input
                type="text"
                value={guardianName}
                placeholder="Full legal name"
                disabled={verifying}
                onChange={(event) => setGuardianName(event.target.value)}
              />
            </label>
            <label className="setting-field">
              <span>Relationship to the child</span>
              <select
                value={relationship}
                disabled={verifying}
                onChange={(event) => setRelationship(event.target.value)}
              >
                <option value="">Select relationship</option>
                {GUARDIAN_RELATIONSHIP_OPTIONS.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {passwordProvider ? (
            <label className="setting-field setting-field-full">
              <span>Confirm your identity — current password</span>
              <input
                type="password"
                value={password}
                autoComplete="current-password"
                placeholder="Your account password"
                disabled={verifying}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
          ) : (
            <p className="auth-info">
              To verify your identity, you will be asked to re-confirm your
              Google account when you give consent.
            </p>
          )}

          <label
            className={`terms-checkbox-label ${
              hasScrolledToBottom ? "" : "terms-checkbox-label-disabled"
            }`}
          >
            <input
              type="checkbox"
              checked={declared}
              disabled={!hasScrolledToBottom || verifying}
              onChange={(event) => setDeclared(event.target.checked)}
            />
            <span>{parentalConsentDeclaration(childName)}</span>
          </label>

          {error && <p className="error-text">{error}</p>}

          <div className="terms-modal-actions">
            <button
              type="button"
              className="bill-editor-secondary"
              onClick={onCancel}
              disabled={verifying}
            >
              Cancel
            </button>
            <button
              type="button"
              className="analyze-btn"
              onClick={handleConfirm}
              disabled={!canConfirm}
            >
              {verifying ? "Verifying..." : "Verify & give consent"}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
