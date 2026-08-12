import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import BackLink from "../components/BackLink";
import { useAuth } from "../context/AuthContext";

const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.35 },
};

const SUPPORT_EMAIL = "app.swaasth@gmail.com";
const DELETION_MAILTO = `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(
  "Swaasth account deletion request"
)}&body=${encodeURIComponent(
  "Please delete my Swaasth account and all associated personal data.\n\nAccount email: \nApproximate date of account creation (if known): \nAdditional details: \n"
)}`;

export default function AccountDeletionRequestPage() {
  const { user, loading } = useAuth();

  return (
    <motion.div className="check-page" {...pageTransition}>
      <main className="check-wrap account-wrap">
        <div className="history-nav">
          <BackLink fallback="/">← Home</BackLink>
        </div>

        <header className="check-header">
          <h1>Delete your Swaasth account</h1>
          <p>
            Request permanent deletion of your account and associated personal
            data under the Digital Personal Data Protection Act, 2023, and Google
            Play account-deletion requirements.
          </p>
        </header>

        <section className="account-section">
          <h2>What is deleted</h2>
          <p className="account-section-copy">
            When your account is deleted, we remove your sign-in credentials,
            patient profiles, hospitals, clinical history, saved analysis
            reports, medical documents, consent records, and encrypted local
            copies of that data on devices where you complete deletion in the
            app.
          </p>
          <p className="account-section-copy">
            Original uploaded files are already discarded after analysis.
            Limited anonymised operational records may be retained where
            required or permitted by law.
          </p>
        </section>

        <section className="account-section">
          <h2>Delete in the app</h2>
          <p className="account-section-copy">
            Signed-in users can delete immediately from Account settings →
            Delete account. You will confirm your identity, then your Auth
            account and data are erased.
          </p>
          {!loading && user ? (
            <Link to="/account/delete" className="patients-manage-link">
              Continue to in-app account deletion →
            </Link>
          ) : (
            <Link
              to="/login"
              state={{ from: { pathname: "/account/delete" } }}
              className="patients-manage-link"
            >
              Sign in to delete your account →
            </Link>
          )}
        </section>

        <section className="account-section">
          <h2>Request deletion by email</h2>
          <p className="account-section-copy">
            If you cannot sign in, or prefer not to use the in-app flow, email
            us from the address linked to your account. We will verify your
            identity and delete the account and associated data within a
            reasonable time, usually within 30 days.
          </p>
          <p className="account-section-copy">
            Include the email address for the account and any details that help
            us locate it.
          </p>
          <a href={DELETION_MAILTO} className="patients-manage-link">
            Email {SUPPORT_EMAIL} →
          </a>
        </section>

        <section className="account-section">
          <h2>Related</h2>
          <Link to="/privacy" className="patients-manage-link">
            Privacy Policy →
          </Link>
          <br />
          <Link to="/terms" className="patients-manage-link">
            Terms and Conditions →
          </Link>
        </section>
      </main>
    </motion.div>
  );
}
