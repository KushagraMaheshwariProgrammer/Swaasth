import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import BackLink from "../components/BackLink";
import BillResults from "../components/BillResults";
import PrescriptionResults from "../components/PrescriptionResults";
import {
  buildPatientNameMap,
  computeBillSummary,
  formatCurrency,
  getBillPatientName,
} from "../billUtils";
import { useAuth } from "../context/AuthContext";
import { POSSIBLE_OVERCHARGE_LABEL } from "../data/hedgingCopy";
import { resolveResultsView } from "../data/reportExport";
import {
  deleteBill,
  getBill,
  getBillSortTime,
  getPendingBillSyncMessage,
  getUserBills,
  getUserBillsLocalSnapshot,
} from "../services/bills";
import { getPatients, getPatientsLocalSnapshot } from "../services/patients";
import { canViewMedicalHistory, patientAllowsHistory, resolveAccountConsent } from "../utils/medicalHistoryConsent";

const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.35 },
};

function billDisplayTitle(bill) {
  return bill.filename || bill.hospital?.name_from_bill || "Hospital bill";
}

function formatBillDate(bill) {
  const sortTime = getBillSortTime(bill);
  if (!sortTime) {
    return "Unknown date";
  }
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(sortTime));
}

function reportKindLabel(bill) {
  if (bill.report_kind === "bundle") {
    const count = bill.source_documents?.length;
    return count ? `${count} documents` : "Multi-document session";
  }
  if (bill.report_kind === "prescription") {
    return "Prescription review";
  }
  if (bill.report_kind === "clinical") {
    return "Clinical review";
  }
  if (bill.report_kind === "combined") {
    return "Bill + prescription review";
  }
  return `${bill.line_items?.length || 0} items`;
}

export default function HistoryPage() {
  const { billId } = useParams();
  const {
    user,
    medicalHistoryConsentAccepted,
    medicalHistoryConsentLoading,
  } = useAuth();
  const navigate = useNavigate();
  const [bills, setBills] = useState([]);
  const [patients, setPatients] = useState([]);
  const [patientNameById, setPatientNameById] = useState({});
  const [selectedBill, setSelectedBill] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncMessage, setSyncMessage] = useState("");
  const [error, setError] = useState("");
  const [deletingBillId, setDeletingBillId] = useState(null);

  const handleDeleteBill = async (bill) => {
    if (!user?.uid || !bill?.id) {
      return;
    }
    const title = billDisplayTitle(bill);
    if (
      !window.confirm(
        `Permanently delete this bill?\n\n${title}\nBill ID: ${bill.id}\n\nThis action cannot be undone.`
      )
    ) {
      return;
    }
    setDeletingBillId(bill.id);
    setError("");
    try {
      await deleteBill(user.uid, bill.id);
      if (billId === bill.id) {
        navigate("/history");
      } else {
        setBills((prev) => prev.filter((entry) => entry.id !== bill.id));
      }
    } catch (err) {
      setError(err.message || "Unable to delete bill.");
    } finally {
      setDeletingBillId(null);
    }
  };

  const accountConsent = resolveAccountConsent(
    user?.uid,
    medicalHistoryConsentAccepted,
    { loading: medicalHistoryConsentLoading }
  );
  const historyAllowed = canViewMedicalHistory(accountConsent);
  const consentedPatientIds = new Set(
    patients.filter((patient) => patientAllowsHistory(patient)).map((p) => p.id)
  );
  const visibleBills = bills.filter((bill) => {
    const patientId = bill.patientId || bill.patient?.id;
    return !patientId || consentedPatientIds.has(patientId);
  });

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      if (!user) {
        return;
      }
      setError("");
      setSyncMessage("");
      try {
        if (billId) {
          setLoading(true);
          const bill = await getBill(user.uid, billId);
          if (cancelled) {
            return;
          }
          if (!bill) {
            setError("Bill not found.");
            setSelectedBill(null);
          } else {
            setSelectedBill(bill);
          }
        } else {
          const localSnapshot = getUserBillsLocalSnapshot(user.uid);
          if (localSnapshot.length) {
            setBills(localSnapshot);
            setLoading(false);
          } else {
            setLoading(true);
          }
          const localPatients = getPatientsLocalSnapshot(user.uid);
          if (localPatients.length) {
            setPatients(localPatients);
            setPatientNameById(buildPatientNameMap(localPatients));
          }
          const [entries, patients] = await Promise.all([
            getUserBills(user.uid),
            getPatients(user.uid),
          ]);
          if (cancelled) {
            return;
          }
          setPatientNameById(buildPatientNameMap(patients));
          setPatients(patients);
          const pendingLocal = entries.filter((bill) => bill.localOnly).length;
          const syncMessage = getPendingBillSyncMessage(pendingLocal);
          if (syncMessage) {
            setSyncMessage(syncMessage);
          }
          setBills(entries);
          setSelectedBill(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Unable to load your bills.");
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
  }, [user, billId]);

  return (
    <motion.div className="check-page" {...pageTransition}>
      <main className="check-wrap history-wrap">
        <div className="history-nav">
          <BackLink fallback="/check" />
          {billId ? (
            <Link to="/history" className="back-link">
              All bills
            </Link>
          ) : null}
        </div>

        <header className="check-header">
          <h1>{billId ? "Bill details" : "Your past bills"}</h1>
          <p>
            {billId
              ? "Review a saved analysis from your account."
              : historyAllowed
              ? "Saved reports from patients who opted in to medical history."
              : "Enable medical history consent to view saved reports."}
          </p>
        </header>

        {medicalHistoryConsentLoading && (
          <p className="history-status">Loading consent settings...</p>
        )}

        {!medicalHistoryConsentLoading && !historyAllowed && !billId && (
          <section className="history-empty">
            <p>
              Medical history is turned off for your account. You can still analyze
              documents, but reports will not be saved until you enable consent.
            </p>
            <Link
              to="/consent/medical-history"
              className="analyze-btn history-empty-cta"
            >
              Manage medical history consent →
            </Link>
          </section>
        )}

        {loading && historyAllowed && (
          <p className="history-status">Loading your bills...</p>
        )}
        {syncMessage && !loading && <p className="auth-info">{syncMessage}</p>}
        {error && <p className="error-text">{error}</p>}

        {!loading && historyAllowed && !billId && !visibleBills.length && !error && (
          <section className="history-empty">
            <p>No saved bills yet for patients with medical history enabled.</p>
            <Link to="/check" className="analyze-btn history-empty-cta">
              Check your first bill →
            </Link>
          </section>
        )}

        {!loading && historyAllowed && !billId && visibleBills.length > 0 && (
          <ul className="history-list">
            {visibleBills.map((bill) => {
              const summary = computeBillSummary(bill);
              const patientName = getBillPatientName(bill, patientNameById);
              const title = billDisplayTitle(bill);
              const isDeleting = deletingBillId === bill.id;
              return (
                <li key={bill.id} className="history-list-row">
                  <button
                    type="button"
                    className="history-card"
                    onClick={() => navigate(`/history/${bill.id}`)}
                  >
                    <div className="history-card-top">
                      <strong>{title}</strong>
                      <span>{formatBillDate(bill)}</span>
                    </div>
                    <p className="history-card-meta">
                      {patientName ? (
                        <>
                          Patient: <strong>{patientName}</strong>
                          {" · "}
                        </>
                      ) : null}
                      {bill.comparison_settings?.city &&
                      bill.comparison_settings?.state_name
                        ? `${bill.comparison_settings.city}, ${bill.comparison_settings.state_name}`
                        : "Location not recorded"}
                      {" · "}
                      {reportKindLabel(bill)}
                      {(bill.clinical_context?.symptoms?.length ||
                        bill.clinical_context?.test_results?.length) > 0 && (
                        <span className="history-clinical-badge">Clinical review</span>
                      )}
                    </p>
                    <div className="history-card-stats">
                      {bill.report_kind === "prescription" ||
                      bill.report_kind === "clinical" ? (
                        <span>
                          {bill.treatment_audit_flags?.flags_count ?? 0} STG flag
                          {(bill.treatment_audit_flags?.flags_count ?? 0) === 1
                            ? ""
                            : "s"}
                        </span>
                      ) : (
                        <>
                          <span>Charged {formatCurrency(summary.totalCharged)}</span>
                          <span className="history-overcharge">
                            {POSSIBLE_OVERCHARGE_LABEL}{" "}
                            {formatCurrency(summary.totalOvercharged)}
                          </span>
                        </>
                      )}
                    </div>
                  </button>
                  <button
                    type="button"
                    className="history-delete-btn"
                    disabled={isDeleting}
                    aria-label={`Delete bill ${title}`}
                    onClick={() => handleDeleteBill(bill)}
                  >
                    {isDeleting ? "Deleting…" : "Delete"}
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        {!loading && billId && selectedBill && (
          <>
            <div className="history-detail-actions">
              <button
                type="button"
                className="history-delete-btn history-delete-btn-prominent"
                disabled={deletingBillId === selectedBill.id}
                onClick={() => handleDeleteBill(selectedBill)}
              >
                {deletingBillId === selectedBill.id
                  ? "Deleting…"
                  : "Delete this bill"}
              </button>
            </div>
            <section className="results-shell">
              {resolveResultsView(selectedBill) === "prescription" ? (
                <PrescriptionResults
                  result={selectedBill}
                  onReportUpdate={setSelectedBill}
                />
              ) : resolveResultsView(selectedBill) === "bill" ? (
                <BillResults
                  result={selectedBill}
                  onReportUpdate={setSelectedBill}
                />
              ) : (
                <p className="auth-info">
                  This saved report does not contain displayable results.
                </p>
              )}
            </section>
          </>
        )}
      </main>
    </motion.div>
  );
}
