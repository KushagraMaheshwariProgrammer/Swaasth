import { motion } from "framer-motion";
import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import BackLink from "../components/BackLink";
import { useAuth, needsEmailVerification as userNeedsEmailVerification } from "../context/AuthContext";
import { recordAdultAttestation } from "../services/userProfile";

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
  if (code === "auth/popup-blocked") {
    return "Your browser blocked the Google sign-in popup. Allow popups for this site and try again.";
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
    signInWithEmail,
    signUpWithEmail,
    signInWithGoogle,
  } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [adultConfirmed, setAdultConfirmed] = useState(false);

  const redirectTo = location.state?.from?.pathname || "/check";
  const accountDeleted = Boolean(location.state?.accountDeleted);

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

    if (mode === "signup" && !adultConfirmed) {
      setError("Confirm that you are 18 years of age or older to create an account.");
      return;
    }

    setIsSubmitting(true);
    try {
      if (mode === "signup") {
        const credential = await signUpWithEmail(email.trim(), password);
        await recordAdultAttestation(credential.user.uid);
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
      setError(getAuthErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setError("");
    setInfo("");
    if (mode === "signup" && !adultConfirmed) {
      setError("Confirm that you are 18 years of age or older to create an account.");
      return;
    }
    setIsSubmitting(true);
    try {
      const credential = await signInWithGoogle();
      if (mode === "signup" && credential?.user?.uid) {
        await recordAdultAttestation(credential.user.uid);
      }
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(getAuthErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <motion.div className="auth-page" {...pageTransition}>
      <main className="auth-wrap">
        <BackLink fallback="/" />

        <section className="auth-card">
          <header className="auth-header">
            <h1>{mode === "signup" ? "Create your account" : "Sign in"}</h1>
            <p>
              {mode === "signup"
                ? "We will send a verification email before you can access your bills."
                : "Save your bill analyses and revisit them anytime from your history."}
            </p>
          </header>

          {accountDeleted && (
            <p className="auth-info">
              Your account and associated data have been permanently deleted.
            </p>
          )}

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
              <>
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
                <label className="complaint-confirm-label">
                  <input
                    type="checkbox"
                    checked={adultConfirmed}
                    onChange={(event) => setAdultConfirmed(event.target.checked)}
                    required
                  />
                  I confirm that I am 18 years of age or older. Swaasth accounts
                  are for adults. A parent or guardian may later add a minor
                  patient profile with parental consent.
                </label>
              </>
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

          <p className="auth-legal-note">
            By continuing, you agree to our{" "}
            <Link to="/terms">Terms and Conditions</Link> and{" "}
            <Link to="/privacy">Privacy Policy</Link>. Corresponding source is
            available under AGPL on the{" "}
            <Link to="/source">Open source</Link> page.
          </p>

          <p className="auth-toggle">
            {mode === "signup" ? "Already have an account?" : "New to Swaasth?"}{" "}
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
