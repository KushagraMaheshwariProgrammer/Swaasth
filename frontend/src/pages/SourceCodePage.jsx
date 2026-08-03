import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import BackLink from "../components/BackLink";
import {
  SOURCE_DEFAULT_BRANCH,
  SOURCE_LICENSE_NAME,
  SOURCE_LICENSE_SPDX,
  SOURCE_OFFER_SUMMARY,
  SOURCE_REPO_URL,
} from "../data/openSource";

const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.35 },
};

export default function SourceCodePage() {
  return (
    <motion.div className="check-page" {...pageTransition}>
      <main className="check-wrap account-wrap">
        <div className="history-nav">
          <BackLink fallback="/" />
        </div>

        <header className="check-header">
          <h1>Open source</h1>
          <p>Last updated: 3 August 2026</p>
        </header>

        <p className="auth-info consent-status-banner">{SOURCE_OFFER_SUMMARY}</p>

        <section className="account-section">
          <h2>Source code offer</h2>
          <p className="account-section-copy">
            This page is the standing offer of corresponding source required when
            Swaasth is used as a network service under the AGPL (including
            components that use MuPDF / PyMuPDF).
          </p>
          <p className="account-section-copy">
            You may obtain, study, modify, and redistribute the source under the
            terms of the AGPL. See the LICENSE file in the repository for the
            full license text.
          </p>
          <ul>
            <li>
              License: {SOURCE_LICENSE_NAME} ({SOURCE_LICENSE_SPDX})
            </li>
            <li>Default branch: {SOURCE_DEFAULT_BRANCH}</li>
            <li>Third-party notices: NOTICE in the repository root</li>
          </ul>
          <a
            className="patients-manage-link"
            href={SOURCE_REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open source repository on GitHub →
          </a>
        </section>

        <section className="account-section">
          <h2>Related</h2>
          <Link to="/terms" className="patients-manage-link">
            Terms and Conditions →
          </Link>
          <br />
          <Link to="/privacy" className="patients-manage-link">
            Privacy Policy →
          </Link>
        </section>
      </main>
    </motion.div>
  );
}
