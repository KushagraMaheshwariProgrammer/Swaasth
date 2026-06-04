import { motion } from "framer-motion";
import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.35 },
};

function getVerificationErrorMessage(error) {
  const code = error?.code || "";
  if (code === "auth/too-many-requests") {
    return "Too many verification emails sent. Please wait a few minutes before trying again.";
  }
  return error?.message || "Unable to send verification email. Please try again.";
}

export default function VerifyEmailPage() {
  const {
    user,
    needsEmailVerification,
    resendVerificationEmail,
    reloadUser,
    logOut,
  } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState("");
  const [info, setInfo] = useState(
    "We sent a verification link to your email. Open it, then return here and continue."
  );
  const [isSubmitting, setIsSubmitting] = useState(false);

  const redirectTo = location.state?.from?.pathname || "/check";
  const emailAddress = user?.email || location.state?.email || "your email";

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.state?.from }} />;
  }

  if (!needsEmailVerification) {
    return <Navigate to={redirectTo} replace />;
  }

  const handleResend = async () => {
    setError("");
    setInfo("");
    setIsSubmitting(true);
    try {
      await resendVerificationEmail();
      setInfo("Verification email sent again. Check your inbox and spam folder.");
    } catch (err) {
      setError(getVerificationErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleContinue = async () => {
    setError("");
    setInfo("");
    setIsSubmitting(true);
    try {
      const refreshed = await reloadUser();
      if (refreshed?.emailVerified) {
        navigate(redirectTo, { replace: true });
        return;
      }
      setError("Your email is not verified yet. Open the link in your inbox first.");
    } catch (err) {
      setError(getVerificationErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <motion.div className="auth-page" {...pageTransition}>
      <main className="auth-wrap">
        <Link to="/" className="back-link">
          ← Back
        </Link>

        <section className="auth-card">
          <header className="auth-header">
            <h1>Verify your email</h1>
            <p>
              We sent a verification email to <strong>{emailAddress}</strong>.
              Click the link in that message to activate your account.
            </p>
          </header>

          <div className="verify-steps">
            <p>1. Check your inbox (and spam folder).</p>
            <p>2. Click the verification link in the email from Firebase.</p>
            <p>3. Return here and press Continue.</p>
          </div>

          <div className="auth-form">
            <button
              type="button"
              className="analyze-btn auth-submit-btn"
              onClick={handleContinue}
              disabled={isSubmitting}
            >
              {isSubmitting ? "Checking..." : "I've verified — Continue"}
            </button>
            <button
              type="button"
              className="bill-editor-secondary verify-resend-btn"
              onClick={handleResend}
              disabled={isSubmitting}
            >
              Resend verification email
            </button>
            <button
              type="button"
              className="auth-toggle-btn verify-signout-btn"
              onClick={() => logOut()}
              disabled={isSubmitting}
            >
              Sign out
            </button>
          </div>

          {info && <p className="auth-info">{info}</p>}
          {error && <p className="error-text">{error}</p>}
        </section>
      </main>
    </motion.div>
  );
}
