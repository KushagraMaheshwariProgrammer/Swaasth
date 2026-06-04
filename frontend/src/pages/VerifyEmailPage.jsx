import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { getVerificationErrorMessage } from "../auth/emailVerification";
import { useAuth } from "../context/AuthContext";

const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.35 },
};

export default function VerifyEmailPage() {
  const {
    user,
    loading,
    needsEmailVerification,
    resendVerificationEmail,
    reloadUser,
    logOut,
    emailLinkVerification,
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
  const isProcessingLink = emailLinkVerification.status === "processing";
  const linkVerified = emailLinkVerification.status === "success";

  useEffect(() => {
    if (emailLinkVerification.status === "success") {
      setInfo(emailLinkVerification.message);
      setError("");
      return;
    }
    if (emailLinkVerification.status === "error") {
      setError(emailLinkVerification.message);
      setInfo("");
    }
  }, [emailLinkVerification]);

  useEffect(() => {
    if (linkVerified && user && !needsEmailVerification) {
      navigate(redirectTo, { replace: true });
    }
  }, [linkVerified, user, needsEmailVerification, navigate, redirectTo]);

  if (loading || isProcessingLink) {
    return (
      <div className="auth-loading">
        <div className="spinner-conic" aria-hidden="true" />
        <p>{isProcessingLink ? "Verifying your email..." : "Loading your account..."}</p>
      </div>
    );
  }

  if (!user && !linkVerified && emailLinkVerification.status !== "error") {
    return <Navigate to="/login" replace state={{ from: location.state?.from }} />;
  }

  if (user && !needsEmailVerification) {
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
            {user ? (
              <p>
                We sent a verification email to <strong>{emailAddress}</strong>.
                Click the link in that message to activate your account.
              </p>
            ) : (
              <p>
                Your email address has been verified. Sign in to continue using BillCheck.
              </p>
            )}
          </header>

          {user && (
            <>
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
            </>
          )}

          {!user && (
            <div className="auth-form">
              <Link to="/login" className="analyze-btn auth-submit-btn">
                Sign in
              </Link>
            </div>
          )}

          {info && <p className="auth-info">{info}</p>}
          {error && <p className="error-text">{error}</p>}
        </section>
      </main>
    </motion.div>
  );
}
