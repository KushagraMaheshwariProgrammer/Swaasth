import { motion } from "framer-motion";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getAccountErrorMessage } from "../auth/accountSecurity";
import BackLink from "../components/BackLink";
import { useAuth } from "../context/AuthContext";

const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.35 },
};

const CONFIRM_PHRASE = "DELETE";

export default function DeleteAccountPage() {
  const {
    user,
    usesPasswordProvider,
    deleteAccount,
  } = useAuth();
  const navigate = useNavigate();

  const [password, setPassword] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const canSubmit =
    acknowledged &&
    confirmText.trim().toUpperCase() === CONFIRM_PHRASE &&
    (!usesPasswordProvider || password.length > 0) &&
    !submitting;

  const handleDelete = async (event) => {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    if (
      !window.confirm(
        "This permanently deletes your Swaasth account and all associated data. This cannot be undone. Continue?"
      )
    ) {
      return;
    }

    setError("");
    setSubmitting(true);
    try {
      await deleteAccount(usesPasswordProvider ? password : undefined);
      navigate("/login", {
        replace: true,
        state: { accountDeleted: true },
      });
    } catch (err) {
      setError(getAccountErrorMessage(err));
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
          <h1>Delete account</h1>
          <p>
            Permanently erase your Swaasth account (
            <strong>{user?.email || "your account"}</strong>) and all data we
            hold for it.
          </p>
        </header>

        <section className="account-section">
          <h2>What will be deleted</h2>
          <p className="account-section-copy">
            Deletion is permanent and cannot be undone. The following will be
            removed:
          </p>
          <ul className="account-delete-list">
            <li>Your Firebase sign-in account</li>
            <li>Patient profiles, hospitals, and clinical history</li>
            <li>Saved analysis reports and medical documents</li>
            <li>Consent and terms records tied to this account</li>
            <li>Encrypted local copies of that data on this device</li>
          </ul>
          <p className="account-section-copy">
            Uploaded document files are already discarded after analysis and are
            not retained. Some anonymised operational logs may be kept where
            required or permitted by law.
          </p>
          <p className="account-section-copy">
            Prefer to keep your account but stop saving reports?{" "}
            <Link to="/consent/medical-history">
              Revoke medical history consent
            </Link>{" "}
            instead.
          </p>
        </section>

        <section className="account-section">
          <h2>Confirm deletion</h2>
          <form className="auth-form" onSubmit={handleDelete}>
            <label className="terms-checkbox-label">
              <input
                type="checkbox"
                checked={acknowledged}
                disabled={submitting}
                onChange={(event) => setAcknowledged(event.target.checked)}
              />
              <span>
                I understand this permanently deletes my account and data, and
                cannot be undone.
              </span>
            </label>

            <label className="setting-field setting-field-full">
              <span>
                Type <strong>{CONFIRM_PHRASE}</strong> to confirm
              </span>
              <input
                type="text"
                autoComplete="off"
                value={confirmText}
                disabled={submitting}
                onChange={(event) => setConfirmText(event.target.value)}
                required
              />
            </label>

            {usesPasswordProvider ? (
              <label className="setting-field setting-field-full">
                <span>Current password</span>
                <input
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  disabled={submitting}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </label>
            ) : (
              <p className="auth-info">
                To verify your identity, you will re-confirm your Google account
                when you delete.
              </p>
            )}

            <button
              type="submit"
              className="history-delete-btn history-delete-btn-prominent account-delete-submit"
              disabled={!canSubmit}
            >
              {submitting ? "Deleting account..." : "Delete my account"}
            </button>
          </form>
          {error && <p className="error-text">{error}</p>}
        </section>
      </main>
    </motion.div>
  );
}
