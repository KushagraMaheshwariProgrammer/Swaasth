import { motion } from "framer-motion";
import { useState } from "react";
import { Link } from "react-router-dom";
import { getAccountErrorMessage } from "../auth/accountSecurity";
import BackLink from "../components/BackLink";
import { useAuth } from "../context/AuthContext";
import { downloadJsonFile, exportUserData } from "../services/dataExport";

const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.35 },
};

function PasswordField({ label, value, onChange, autoComplete }) {
  return (
    <label className="setting-field setting-field-full">
      <span>{label}</span>
      <input
        type="password"
        autoComplete={autoComplete}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required
        minLength={6}
      />
    </label>
  );
}

export default function AccountSettingsPage() {
  const {
    user,
    usesPasswordProvider,
    changePassword,
    changeEmail,
    medicalHistoryConsentAccepted,
  } = useAuth();

  const [passwordForm, setPasswordForm] = useState({
    current: "",
    next: "",
    confirm: "",
  });
  const [emailForm, setEmailForm] = useState({
    currentPassword: "",
    nextEmail: "",
  });

  const [passwordInfo, setPasswordInfo] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [emailInfo, setEmailInfo] = useState("");
  const [emailError, setEmailError] = useState("");

  const [passwordSubmitting, setPasswordSubmitting] = useState(false);
  const [emailSubmitting, setEmailSubmitting] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportMessage, setExportMessage] = useState("");
  const [exportError, setExportError] = useState("");

  const handlePasswordChange = async (event) => {
    event.preventDefault();
    setPasswordInfo("");
    setPasswordError("");

    if (passwordForm.next !== passwordForm.confirm) {
      setPasswordError("New passwords do not match.");
      return;
    }

    setPasswordSubmitting(true);
    try {
      await changePassword(passwordForm.current, passwordForm.next);
      setPasswordForm({ current: "", next: "", confirm: "" });
      setPasswordInfo("Password updated successfully.");
    } catch (error) {
      setPasswordError(getAccountErrorMessage(error));
    } finally {
      setPasswordSubmitting(false);
    }
  };

  const handleEmailChange = async (event) => {
    event.preventDefault();
    setEmailInfo("");
    setEmailError("");

    setEmailSubmitting(true);
    try {
      await changeEmail(emailForm.currentPassword, emailForm.nextEmail);
      setEmailForm({ currentPassword: "", nextEmail: "" });
      setEmailInfo(
        "Verification email sent to your new address. Open that link to finish the change."
      );
    } catch (error) {
      setEmailError(getAccountErrorMessage(error));
    } finally {
      setEmailSubmitting(false);
    }
  };

  const handleDownloadMyData = async () => {
    if (!user?.uid) {
      return;
    }
    setExportBusy(true);
    setExportMessage("");
    setExportError("");
    try {
      const payload = await exportUserData(user.uid);
      downloadJsonFile(`swaasth-data-export-${user.uid.slice(0, 8)}.json`, payload);
      setExportMessage("Your data export downloaded. Keep this file private.");
    } catch (error) {
      setExportError(error?.message || "Could not export your data.");
    } finally {
      setExportBusy(false);
    }
  };

  const identityLabel = usesPasswordProvider
    ? "Email and password"
    : "Google sign-in";

  return (
    <motion.div className="check-page" {...pageTransition}>
      <main className="check-wrap account-wrap">
        <div className="history-nav">
          <BackLink fallback="/check" />
        </div>

        <header className="check-header">
          <h1>Account settings</h1>
          <p>
            Signed in as <strong>{user?.email || "your account"}</strong> via {identityLabel}.
          </p>
        </header>

        <section className="account-section">
          <h2>Legal</h2>
          <p className="account-section-copy">
            Review the agreements that govern your use of Swaasth and how your
            data is handled.
          </p>
          <Link to="/terms" className="patients-manage-link">
            Terms and Conditions →
          </Link>
          <br />
          <Link to="/privacy" className="patients-manage-link">
            Privacy Policy →
          </Link>
          <br />
          <Link to="/source" className="patients-manage-link">
            Open source / corresponding source →
          </Link>
          <br />
          <Link to="/licenses" className="patients-manage-link">
            Third-party licenses →
          </Link>
        </section>

        <section className="account-section">
          <h2>Your data</h2>
          <p className="account-section-copy">
            Download a copy of the personal data Swaasth holds for this account
            (profile, consents, patients, hospitals, and saved reports). To
            nominate someone to exercise your rights if you die or become
            incapacitated, email app.swaasth@gmail.com from this account.
          </p>
          <button
            type="button"
            className="bill-editor-secondary"
            onClick={handleDownloadMyData}
            disabled={exportBusy}
          >
            {exportBusy ? "Preparing export…" : "Download my data"}
          </button>
          {exportMessage && <p className="auth-info">{exportMessage}</p>}
          {exportError && <p className="error-text">{exportError}</p>}
        </section>

        <section className="account-section">
          <h2>Medical history</h2>
          <p className="account-section-copy">
            {medicalHistoryConsentAccepted
              ? "Medical history is enabled. Reports can be saved for patients who opt in."
              : "Medical history is off. You can analyze documents, but reports will not be saved."}
          </p>
          <Link to="/consent/medical-history" className="patients-manage-link">
            Manage medical history consent →
          </Link>
        </section>

        {usesPasswordProvider && (
          <section className="account-section">
            <h2>Change password</h2>
            <p className="account-section-copy">
              Choose a new password with at least 6 characters.
            </p>
            <form className="auth-form" onSubmit={handlePasswordChange}>
              <PasswordField
                label="Current password"
                value={passwordForm.current}
                onChange={(value) => setPasswordForm((prev) => ({ ...prev, current: value }))}
                autoComplete="current-password"
              />
              <PasswordField
                label="New password"
                value={passwordForm.next}
                onChange={(value) => setPasswordForm((prev) => ({ ...prev, next: value }))}
                autoComplete="new-password"
              />
              <PasswordField
                label="Confirm new password"
                value={passwordForm.confirm}
                onChange={(value) => setPasswordForm((prev) => ({ ...prev, confirm: value }))}
                autoComplete="new-password"
              />
              <button
                type="submit"
                className="analyze-btn auth-submit-btn"
                disabled={passwordSubmitting}
              >
                {passwordSubmitting ? "Updating..." : "Update password"}
              </button>
            </form>
            {passwordInfo && <p className="auth-info">{passwordInfo}</p>}
            {passwordError && <p className="error-text">{passwordError}</p>}
          </section>
        )}

        {usesPasswordProvider && (
          <section className="account-section">
            <h2>Change email address</h2>
            <p className="account-section-copy">
              We will send a verification link to your new email before the change takes effect.
            </p>
            <form className="auth-form" onSubmit={handleEmailChange}>
              <label className="setting-field setting-field-full">
                <span>New email</span>
                <input
                  type="email"
                  autoComplete="email"
                  value={emailForm.nextEmail}
                  onChange={(event) =>
                    setEmailForm((prev) => ({ ...prev, nextEmail: event.target.value }))
                  }
                  required
                />
              </label>
              <PasswordField
                label="Current password"
                value={emailForm.currentPassword}
                onChange={(value) =>
                  setEmailForm((prev) => ({ ...prev, currentPassword: value }))
                }
                autoComplete="current-password"
              />
              <button
                type="submit"
                className="analyze-btn auth-submit-btn"
                disabled={emailSubmitting}
              >
                {emailSubmitting ? "Sending..." : "Send verification to new email"}
              </button>
            </form>
            {emailInfo && <p className="auth-info">{emailInfo}</p>}
            {emailError && <p className="error-text">{emailError}</p>}
          </section>
        )}

        {!usesPasswordProvider && (
          <section className="account-section">
            <p className="account-section-copy">
              Your email and sign-in method are managed through Google. Use your Google account
              settings to update them.
            </p>
          </section>
        )}

        <section className="account-section account-section-danger">
          <h2>Delete account</h2>
          <p className="account-section-copy">
            Permanently delete your Swaasth account, patient profiles, saved
            reports, and local encrypted copies. This cannot be undone.
          </p>
          <Link to="/account/delete" className="patients-manage-link">
            Delete my account →
          </Link>
          <br />
          <Link to="/delete-account" className="patients-manage-link">
            Web deletion request page →
          </Link>
        </section>
      </main>
    </motion.div>
  );
}
