import { motion } from "framer-motion";
import BackLink from "./BackLink";

const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.35 },
};

export default function LegalDocument({ title, lastUpdated, sections, lead }) {
  return (
    <motion.div className="check-page" {...pageTransition}>
      <main className="check-wrap account-wrap">
        <div className="history-nav">
          <BackLink fallback="/" />
        </div>

        <header className="check-header">
          <h1>{title}</h1>
          <p>Last updated: {lastUpdated}</p>
        </header>

        {lead && <p className="auth-info consent-status-banner">{lead}</p>}

        <section className="account-section terms-section-stack">
          {sections.map((section) => (
            <section key={section.title} className="terms-section">
              <h2>{section.title}</h2>
              {section.paragraphs.map((paragraph, index) => (
                <p key={`${section.title}-p-${index}`}>{paragraph}</p>
              ))}
              {section.bullets.length > 0 && (
                <ul>
                  {section.bullets.map((item, index) => (
                    <li key={`${section.title}-b-${index}`}>{item}</li>
                  ))}
                </ul>
              )}
            </section>
          ))}
        </section>
      </main>
    </motion.div>
  );
}
