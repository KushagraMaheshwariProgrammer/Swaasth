import { motion } from "framer-motion";
import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { getAccountErrorMessage } from "../auth/accountSecurity";
import { useAuth, needsEmailVerification as userNeedsEmailVerification } from "../context/AuthContext";

const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.35 },
};

function getAuthErrorMessage(error) {
  const code = error?.code || "";
  if (code === "auth/configuration-not-found") {
    return "Google sign-in is not enabled in Firebase yet. Open Firebase Console → Authentication → Sign-in method, click Get started if needed, then enable Google and Email/Password.";
  }
  if (code === "auth/email-already-in-use") {
    return "An account with this email already exists. Try signing in instead.";
  }
  if (code === "auth/invalid-email") {
    return "Please enter a valid email address.";
  }
  if (code === "auth/weak-password") {
    return "Password must be at least 6 characters.";
  }
  if (code === "auth/user-not-found" || code === "auth/wrong-password") {
    return "Invalid email or password.";
  }
  if (code === "auth/invalid-credential") {
    return "Invalid email or password.";
  }
  if (code === "auth/popup-closed-by-user") {
    return "Google sign-in was cancelled.";
  }
  if (code === "auth/too-many-requests") {
    return "Too many attempts. Please wait a few minutes and try again.";
  }
  return error?.message || "Unable to authenticate. Please try again.";
}

export default function LoginPage() {
  const {
    user,
    needsEmailVerification,
    mfaResolver,
    signInWithEmail,
    signUpWithEmail,
    signInWithGoogle,
    completeMfaSignIn,
    cancelMfaSignIn,
  } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const redirectTo = location.state?.from?.pathname || "/check";

  if (user && needsEmailVerification) {
    return <Navigate to="/verify-email" replace state={{ from: location.state?.from }} />;
  }

  if (user) {
    return <Navigate to={redirectTo} replace />;
  }

  const resetFormFields = (nextMode) => {
    setMode(nextMode);
    setError("");
    setInfo("");
    setConfirmPassword("");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setInfo("");

    if (mode === "signup" && password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);
    try {
      if (mode === "signup") {
        await signUpWithEmail(email.trim(), password);
        navigate("/verify-email", {
          replace: true,
          state: { from: location.state?.from, email: email.trim() },
        });
        return;
      }

      const credential = await signInWithEmail(email.trim(), password);
      if (userNeedsEmailVerification(credential.user)) {
        navigate("/verify-email", {
          replace: true,
          state: { from: location.state?.from, email: email.trim() },
        });
        return;
      }
      navigate(redirectTo, { replace: true });
    } catch (err) {
      if (err?.code === "auth/multi-factor-auth-required") {
        setError("");
        return;
      }
      setError(getAuthErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setError("");
    setInfo("");
    setIsSubmitting(true);
    try {
      const result = await signInWithGoogle();
      if (result) {
        navigate(redirectTo, { replace: true });
      } else {
        setInfo("Redirecting to Google sign-in...");
      }
    } catch (err) {
      if (err?.code === "auth/multi-factor-auth-required") {
        setError("");
        return;
      }
      setError(getAuthErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleMfaSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setInfo("");
    setIsSubmitting(true);
    try {
      const credential = await completeMfaSignIn(mfaCode);
      if (userNeedsEmailVerification(credential.user)) {
        navigate("/verify-email", {
          replace: true,
          state: { from: location.state?.from, email: credential.user.email || email.trim() },
        });
        return;
      }
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(getAccountErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (mfaResolver) {
    return (
      <motion.div className="auth-page" {...pageTransition}>
        <main className="auth-wrap">
          <Link to="/" className="back-link">
            ← Back
          </Link>

          <section className="auth-card">
            <header className="auth-header">
              <h1>Two-factor authentication</h1>
              <p>Enter the 6-digit code from your authenticator app to finish signing in.</p>
            </header>

            <form className="auth-form" onSubmit={handleMfaSubmit}>
              <label className="setting-field setting-field-full">
                <span>Authentication code</span>
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
                disabled={isSubmitting || mfaCode.length !== 6}
              >
                {isSubmitting ? "Verifying..." : "Verify and sign in"}
              </button>
              <button
                type="button"
                className="auth-toggle-btn"
                onClick={() => {
                  cancelMfaSignIn();
                  setMfaCode("");
                  setError("");
                }}
                disabled={isSubmitting}
              >
                Back to sign in
              </button>
            </form>

            {error && <p className="error-text">{error}</p>}
          </section>
        </main>
      </motion.div>
    );
  }

  return (
    <motion.div className="auth-page" {...pageTransition}>
      <main className="auth-wrap">
        <Link to="/" className="back-link">
          ← Back
        </Link>

        <section className="auth-card">
          <header className="auth-header">
            <h1>{mode === "signup" ? "Create your account" : "Sign in"}</h1>
            <p>
              {mode === "signup"
                ? "We will send a verification email before you can access your bills."
                : "Save your bill analyses and revisit them anytime from your history."}
            </p>
          </header>

          <button
            type="button"
            className="google-auth-btn"
            onClick={handleGoogleSignIn}
            disabled={isSubmitting}
          >
            Continue with Google
          </button>

          <div className="auth-divider">
            <span>or</span>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            <label className="setting-field setting-field-full">
              <span>Email</span>
              <input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </label>
            <label className="setting-field setting-field-full">
              <span>Password</span>
              <input
                type="password"
                autoComplete={mode === "signup" ? "new-password" : "current-password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                minLength={6}
                required
              />
            </label>
            {mode === "signup" && (
              <label className="setting-field setting-field-full">
                <span>Confirm password</span>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  minLength={6}
                  required
                />
              </label>
            )}

            <button
              type="submit"
              className="analyze-btn auth-submit-btn"
              disabled={isSubmitting}
            >
              {isSubmitting
                ? "Please wait..."
                : mode === "signup"
                ? "Create account"
                : "Sign in"}
            </button>
          </form>

          {info && <p className="auth-info">{info}</p>}
          {error && <p className="error-text">{error}</p>}

          <p className="auth-toggle">
            {mode === "signup" ? "Already have an account?" : "New to BillCheck?"}{" "}
            <button
              type="button"
              className="auth-toggle-btn"
              onClick={() =>
                resetFormFields(mode === "signup" ? "signin" : "signup")
              }
            >
              {mode === "signup" ? "Sign in" : "Create account"}
            </button>
          </p>
        </section>
      </main>
    </motion.div>
  );
}
