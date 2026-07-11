import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import {
  MEDICAL_HISTORY_CONSENT_LAST_UPDATED,
  MEDICAL_HISTORY_CONSENT_SECTIONS,
} from "../data/medicalHistoryConsent";
import BackLink from "../components/BackLink";
import { useAuth } from "../context/AuthContext";

const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.35 },
};

export default function MedicalHistoryConsentPage() {
  const {
    medicalHistoryConsentAccepted,
    medicalHistoryConsentLoading,
    acceptMedicalHistoryConsent,
    declineMedicalHistoryConsent,
    revokeMedicalHistoryConsent,
  } = useAuth();
  const [agreed, setAgreed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  useEffect(() => {
    setAgreed(Boolean(medicalHistoryConsentAccepted));
  }, [medicalHistoryConsentAccepted]);

  const handleAccept = async () => {
    if (!agreed) {
      setError("Please check the consent box to enable medical history.");
      return;
    }
    setError("");
    setInfo("");
    setSubmitting(true);
    try {
      await acceptMedicalHistoryConsent();
      setInfo("Medical history saving is now enabled for your account.");
    } catch (err) {
      setError(err?.message || "Could not save your consent.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDecline = async () => {
    setError("");
    setInfo("");
    setSubmitting(true);
    try {
      await declineMedicalHistoryConsent();
      setAgreed(false);
      setInfo(
        "Medical history saving is disabled. You can still analyze documents without saving reports."
      );
    } catch (err) {
      setError(err?.message || "Could not update your preference.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRevoke = async () => {
    if (
      !window.confirm(
        "Revoke medical history consent? New reports will not be saved. Previously saved reports remain until you delete them."
      )
    ) {
      return;
    }
    setError("");
    setInfo("");
    setSubmitting(true);
    try {
      await revokeMedicalHistoryConsent();
      setAgreed(false);
      setInfo(
        "Consent reset. Choose whether to enable or decline medical history below."
      );
    } catch (err) {
      setError(err?.message || "Could not revoke consent.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <motion.div className="check-page" {...pageTransition}>
      <main className="check-wrap account-wrap">
        <div className="history-nav">
          <BackLink fallback="/account">← Account settings</BackLink>
        </div>

        <header className="check-header">
          <h1>Medical history consent</h1>
          <p>Last updated: {MEDICAL_HISTORY_CONSENT_LAST_UPDATED}</p>
        </header>

        {medicalHistoryConsentLoading ? (
          <p className="auth-info consent-status-banner">Loading your consent status...</p>
        ) : (
          <p className="auth-info consent-status-banner">
            Status:{" "}
            <strong>
              {medicalHistoryConsentAccepted
                ? "Enabled — reports can be saved"
                : "Disabled — reports are not saved"}
            </strong>
          </p>
        )}

        <section className="account-section terms-section-stack">
          {MEDICAL_HISTORY_CONSENT_SECTIONS.map((section) => (
            <section key={section.title} className="terms-section">
              <h2>{section.title}</h2>
              {section.paragraphs.map((paragraph, index) => (
                <p key={`${section.title}-p-${index}`}>{paragraph}</p>
              ))}
            </section>
          ))}
        </section>

        <section className="account-section">
          <label className="terms-checkbox-label">
            <input
              type="checkbox"
              checked={agreed}
              disabled={submitting}
              onChange={(event) => setAgreed(event.target.checked)}
            />
            <span>
              I consent to saving medical history (analysis reports) to my
              Swaasth account.
            </span>
          </label>

          <div className="terms-modal-actions">
            <button
              type="button"
              className="bill-editor-secondary"
              onClick={handleDecline}
              disabled={submitting}
            >
              Decline saving history
            </button>
            <button
              type="button"
              className="analyze-btn"
              onClick={handleAccept}
              disabled={submitting || !agreed}
            >
              {submitting ? "Saving..." : "Enable medical history"}
            </button>
          </div>

          {medicalHistoryConsentAccepted && (
            <button
              type="button"
              className="bill-editor-secondary consent-revoke-btn"
              onClick={handleRevoke}
              disabled={submitting}
            >
              Reset consent choice
            </button>
          )}

          {info && <p className="auth-info">{info}</p>}
          {error && <p className="error-text">{error}</p>}
        </section>
      </main>
    </motion.div>
  );
}
