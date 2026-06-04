import { motion } from "framer-motion";
import { useState } from "react";
import { Link } from "react-router-dom";
import { getAccountErrorMessage } from "../auth/accountSecurity";
import { useAuth } from "../context/AuthContext";

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
    hasTotpMfa,
    totpFactors,
    changePassword,
    changeEmail,
    startTotpEnrollment,
    finishTotpEnrollment,
    removeTotpMfa,
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
  const [securityPassword, setSecurityPassword] = useState("");
  const [mfaSetup, setMfaSetup] = useState(null);
  const [mfaCode, setMfaCode] = useState("");
  const [disablePassword, setDisablePassword] = useState("");

  const [passwordInfo, setPasswordInfo] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [emailInfo, setEmailInfo] = useState("");
  const [emailError, setEmailError] = useState("");
  const [mfaInfo, setMfaInfo] = useState("");
  const [mfaError, setMfaError] = useState("");

  const [passwordSubmitting, setPasswordSubmitting] = useState(false);
  const [emailSubmitting, setEmailSubmitting] = useState(false);
  const [mfaSubmitting, setMfaSubmitting] = useState(false);

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

  const handleStartMfa = async () => {
    setMfaInfo("");
    setMfaError("");
    setMfaSubmitting(true);
    try {
      const enrollment = await startTotpEnrollment(securityPassword);
      setMfaSetup(enrollment);
      setSecurityPassword("");
      setMfaInfo("Scan the QR code with Google Authenticator, Authy, or a similar app.");
    } catch (error) {
      setMfaError(getAccountErrorMessage(error));
    } finally {
      setMfaSubmitting(false);
    }
  };

  const handleFinishMfa = async (event) => {
    event.preventDefault();
    setMfaInfo("");
    setMfaError("");
    setMfaSubmitting(true);
    try {
      await finishTotpEnrollment(mfaSetup.totpSecret, mfaCode);
      setMfaSetup(null);
      setMfaCode("");
      setMfaInfo("Two-factor authentication is now enabled.");
    } catch (error) {
      setMfaError(getAccountErrorMessage(error));
    } finally {
      setMfaSubmitting(false);
    }
  };

  const handleDisableMfa = async (event) => {
    event.preventDefault();
    setMfaInfo("");
    setMfaError("");
    setMfaSubmitting(true);
    try {
      const factorUid = totpFactors[0]?.uid;
      await removeTotpMfa(factorUid, disablePassword);
      setDisablePassword("");
      setMfaInfo("Two-factor authentication has been disabled.");
    } catch (error) {
      setMfaError(getAccountErrorMessage(error));
    } finally {
      setMfaSubmitting(false);
    }
  };

  const identityLabel = usesPasswordProvider
    ? "Email and password"
    : "Google sign-in";

  return (
    <motion.div className="check-page" {...pageTransition}>
      <main className="check-wrap account-wrap">
        <div className="history-nav">
          <Link to="/check" className="back-link">
            ← Back
          </Link>
        </div>

        <header className="check-header">
          <h1>Account & security</h1>
          <p>
            Signed in as <strong>{user?.email || "your account"}</strong> via {identityLabel}.
          </p>
        </header>

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

        <section className="account-section">
          <h2>Two-factor authentication</h2>
          <p className="account-section-copy">
            Add an authenticator app for a second sign-in step. Required on every login once enabled.
          </p>

          {hasTotpMfa ? (
            <>
              <p className="account-mfa-status">
                Status: <strong>Enabled</strong>
                {totpFactors[0]?.displayName ? ` (${totpFactors[0].displayName})` : ""}
              </p>
              <form className="auth-form" onSubmit={handleDisableMfa}>
                {usesPasswordProvider ? (
                  <PasswordField
                    label="Current password"
                    value={disablePassword}
                    onChange={setDisablePassword}
                    autoComplete="current-password"
                  />
                ) : (
                  <p className="account-section-copy">
                    Confirm with Google when prompted to disable two-factor authentication.
                  </p>
                )}
                <button
                  type="submit"
                  className="bill-editor-secondary account-danger-btn"
                  disabled={mfaSubmitting}
                >
                  {mfaSubmitting ? "Disabling..." : "Disable two-factor authentication"}
                </button>
              </form>
            </>
          ) : mfaSetup ? (
            <form className="auth-form" onSubmit={handleFinishMfa}>
              <div className="account-mfa-qr-wrap">
                <img
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(mfaSetup.qrCodeUrl)}`}
                  alt="Scan with your authenticator app"
                  className="account-mfa-qr"
                  width="180"
                  height="180"
                />
              </div>
              <p className="account-section-copy">
                Or enter this key manually:{" "}
                <code className="account-mfa-secret">{mfaSetup.secretKey}</code>
              </p>
              <label className="setting-field setting-field-full">
                <span>6-digit code from authenticator</span>
                <input
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  value={mfaCode}
                  onChange={(event) => setMfaCode(event.target.value.replace(/\D/g, ""))}
                  required
                />
              </label>
              <button
                type="submit"
                className="analyze-btn auth-submit-btn"
                disabled={mfaSubmitting || mfaCode.length !== 6}
              >
                {mfaSubmitting ? "Verifying..." : "Enable two-factor authentication"}
              </button>
              <button
                type="button"
                className="auth-toggle-btn account-cancel-btn"
                onClick={() => {
                  setMfaSetup(null);
                  setMfaCode("");
                  setMfaInfo("");
                  setMfaError("");
                }}
                disabled={mfaSubmitting}
              >
                Cancel setup
              </button>
            </form>
          ) : (
            <form
              className="auth-form"
              onSubmit={(event) => {
                event.preventDefault();
                handleStartMfa();
              }}
            >
              {usesPasswordProvider ? (
                <PasswordField
                  label="Current password"
                  value={securityPassword}
                  onChange={setSecurityPassword}
                  autoComplete="current-password"
                />
              ) : (
                <p className="account-section-copy">
                  Confirm with Google when prompted to begin setup.
                </p>
              )}
              <button
                type="submit"
                className="analyze-btn auth-submit-btn"
                disabled={mfaSubmitting}
              >
                {mfaSubmitting ? "Starting..." : "Set up authenticator app"}
              </button>
            </form>
          )}

          {mfaInfo && <p className="auth-info">{mfaInfo}</p>}
          {mfaError && <p className="error-text">{mfaError}</p>}
        </section>
      </main>
    </motion.div>
  );
}
