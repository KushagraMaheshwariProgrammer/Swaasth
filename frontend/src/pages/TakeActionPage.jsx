import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import ActionConsentModal from "../components/ActionConsentModal";
import ActionItemsList from "../components/ActionItemsList";
import BackLink from "../components/BackLink";
import ComplaintTemplates from "../components/ComplaintTemplates";
import CombinedNarrative from "../components/CombinedNarrative";
import DischargeGuidance from "../components/DischargeGuidance";
import DisputeTimelineReminders from "../components/DisputeTimelineReminders";
import EscalationLadder from "../components/EscalationLadder";
import RecoverableSummary from "../components/RecoverableSummary";
import { resolveActionPlan } from "../actionPlanUtils";
import { useAuth } from "../context/AuthContext";
import { useNavigateBack } from "../hooks/useNavigateBack";
import { getBill } from "../services/bills";
import { downloadDisputePackPdf } from "../services/reportPdf";
import {
  hasActionConsent,
  setActionConsentAccepted,
} from "../services/localActionConsentStore";

const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.35 },
};

export default function TakeActionPage() {
  const { billId } = useParams();
  const location = useLocation();
  const { user } = useAuth();
  const goBack = useNavigateBack("/check");
  const stateReport = location.state?.report || null;

  const [consentGranted, setConsentGranted] = useState(hasActionConsent);
  const [report, setReport] = useState(stateReport);
  const [loading, setLoading] = useState(Boolean(billId && !stateReport));
  const [error, setError] = useState("");
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfMessage, setPdfMessage] = useState("");
  const [pdfTone, setPdfTone] = useState("error");

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      if (stateReport) {
        setReport(stateReport);
        return;
      }
      if (!billId || !user?.uid) {
        return;
      }
      setLoading(true);
      setError("");
      try {
        const bill = await getBill(user.uid, billId);
        if (cancelled) {
          return;
        }
        if (!bill) {
          setError("We couldn't find this saved report.");
          setReport(null);
        } else {
          setReport(bill);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Unable to load this report.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [billId, stateReport, user]);

  const actionPlan = resolveActionPlan(report);

  const handleConsentAccept = () => {
    setActionConsentAccepted();
    setConsentGranted(true);
  };

  const handleConsentDecline = () => {
    goBack();
  };

  const handleDownloadPack = async () => {
    if (!report) {
      return;
    }
    setPdfBusy(true);
    setPdfMessage("");
    try {
      const outcome = await downloadDisputePackPdf(report);
      if (outcome.method === "share") {
        setPdfTone("info");
        setPdfMessage("Choose an app to save the dispute pack.");
      }
    } catch (err) {
      setPdfTone("error");
      setPdfMessage(
        err?.message ||
          "Could not download the dispute pack. Check your connection and try again."
      );
    } finally {
      setPdfBusy(false);
    }
  };

  if (!consentGranted) {
    return (
      <ActionConsentModal
        onAccept={handleConsentAccept}
        onDecline={handleConsentDecline}
      />
    );
  }

  return (
    <motion.div className="check-page" {...pageTransition}>
      <main className="check-wrap take-action-wrap">
        <div className="history-nav">
          <BackLink fallback="/check" />
          <Link to="/history" className="back-link">
            Your bills
          </Link>
        </div>

        <header className="check-header">
          <h1>Take action / Dispute</h1>
          <p>
            A guided way to seek clarification on your bill. Everything here is
            assistance, not a final medical or legal finding against any hospital
            or doctor.
          </p>
        </header>

        {loading && <p className="history-status">Loading your report…</p>}
        {error && <p className="error-text">{error}</p>}

        {!loading && !report && !error && (
          <section className="history-empty">
            <p>
              We don't have a report to build an action plan from. Check a bill
              first, then choose "Take action / Dispute".
            </p>
            <Link to="/check" className="analyze-btn history-empty-cta">
              Check a bill →
            </Link>
          </section>
        )}

        {!loading && report && !actionPlan && (
          <section className="history-empty">
            <p>
              No items were identified that need clarification for this report.
            </p>
            <Link to="/history" className="analyze-btn history-empty-cta">
              Back to your bills →
            </Link>
          </section>
        )}

        {!loading && report && actionPlan && (
          <section className="results-shell take-action-results">
            <div className="take-action-toolbar">
              <button
                type="button"
                className="analyze-btn"
                onClick={handleDownloadPack}
                disabled={pdfBusy}
              >
                {pdfBusy ? "Preparing…" : "Download dispute pack (PDF)"}
              </button>
            </div>
            {pdfMessage && (
              <p
                className={
                  pdfTone === "info"
                    ? "auth-info report-actions-message"
                    : "error-text report-actions-message"
                }
              >
                {pdfMessage}
              </p>
            )}

            <CombinedNarrative narrative={actionPlan.combined_narrative} />
            <DischargeGuidance
              dischargeGuidance={actionPlan.discharge_guidance}
            />
            <RecoverableSummary
              recoverableEstimate={actionPlan.recoverable_estimate}
            />
            <ActionItemsList actionItems={actionPlan.action_items} />
            <EscalationLadder escalationLadder={actionPlan.escalation_ladder} />
            <DisputeTimelineReminders />
            <ComplaintTemplates
              complaintTemplates={actionPlan.complaint_templates}
            />

            {actionPlan.disclaimer && (
              <p className="treatment-audit-disclaimer take-action-footer">
                {actionPlan.disclaimer}
              </p>
            )}
          </section>
        )}
      </main>
    </motion.div>
  );
}
