import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import BillResults from "../components/BillResults";
import PrescriptionResults from "../components/PrescriptionResults";
import {
  buildPatientNameMap,
  computeBillSummary,
  formatCurrency,
  getBillPatientName,
} from "../billUtils";
import { reportKindLabel } from "../data/reportExport";
import { useAuth } from "../context/AuthContext";
import {
  deleteBill,
  getBill,
  getBillSortTime,
  getPendingBillSyncMessage,
  getUserBills,
  getUserBillsLocalSnapshot,
} from "../services/bills";
import { getPatients, getPatientsLocalSnapshot } from "../services/patients";

const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.35 },
};

function billDisplayTitle(bill) {
  return bill.hospital?.name_from_bill || bill.filename || "Hospital bill";
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

export default function HistoryPage() {
  const { billId } = useParams();
  const { user, medicalHistoryConsentAccepted, medicalHistoryConsentLoading } =
    useAuth();
  const navigate = useNavigate();
  const [bills, setBills] = useState([]);
  const [patientNameById, setPatientNameById] = useState({});
  const [selectedBill, setSelectedBill] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncMessage, setSyncMessage] = useState("");
  const [error, setError] = useState("");
  const [deletingBillId, setDeletingBillId] = useState(null);

  const historyAllowed = Boolean(medicalHistoryConsentAccepted);

  const filterConsentedBills = (entries, patientMap) =>
    entries.filter((bill) => {
      const patientId = bill.patientId || bill.patient?.id;
      if (!patientId) {
        return false;
      }
      const patient = patientMap[patientId];
      return patient?.savePastBills === true;
    });

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

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      if (!user) {
        return;
      }
      if (!historyAllowed) {
        setLoading(false);
        setBills([]);
        setSelectedBill(null);
        return;
      }
      setError("");
      setSyncMessage("");
      try {
        if (billId) {
          setLoading(true);
          const [bill, patients] = await Promise.all([
            getBill(user.uid, billId),
            getPatients(user.uid),
          ]);
          const patientMap = Object.fromEntries(
            patients.map((patient) => [patient.id, patient])
          );
          if (cancelled) {
            return;
          }
          if (!bill) {
            setError("Bill not found.");
            setSelectedBill(null);
          } else if (!filterConsentedBills([bill], patientMap).length) {
            setError("This report is not available without medical history consent.");
            setSelectedBill(null);
          } else {
            setSelectedBill(bill);
          }
        } else {
          const localSnapshot = getUserBillsLocalSnapshot(user.uid);
          const localPatients = getPatientsLocalSnapshot(user.uid);
          const localPatientMap = Object.fromEntries(
            localPatients.map((patient) => [patient.id, patient])
          );
          if (localSnapshot.length) {
            setBills(filterConsentedBills(localSnapshot, localPatientMap));
            setLoading(false);
          } else {
            setLoading(true);
          }
          if (localPatients.length) {
            setPatientNameById(buildPatientNameMap(localPatients));
          }
          const [entries, patients] = await Promise.all([
            getUserBills(user.uid),
            getPatients(user.uid),
          ]);
          if (cancelled) {
            return;
          }
          const patientMap = Object.fromEntries(
            patients.map((patient) => [patient.id, patient])
          );
          setPatientNameById(buildPatientNameMap(patients));
          const visibleBills = filterConsentedBills(entries, patientMap);
          const pendingLocal = visibleBills.filter((bill) => bill.localOnly).length;
          const syncMessage = getPendingBillSyncMessage(pendingLocal);
          if (syncMessage) {
            setSyncMessage(syncMessage);
          }
          setBills(visibleBills);
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
  }, [user, billId, historyAllowed]);

  return (
    <motion.div className="check-page" {...pageTransition}>
      <main className="check-wrap history-wrap">
        <div className="history-nav">
          <Link to="/check" className="back-link">
            ← Check a bill
          </Link>
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
              : "Saved analysis reports from document checks you've opted to store."}
          </p>
        </header>

        {medicalHistoryConsentLoading && (
          <p className="history-status">Loading consent status...</p>
        )}

        {!medicalHistoryConsentLoading && !historyAllowed && (
          <section className="history-empty">
            <p>
              Medical history is disabled for your account. Enable consent to view
              and save past reports.
            </p>
            <Link
              to="/consent/medical-history"
              className="analyze-btn history-empty-cta"
            >
              Manage medical history consent →
            </Link>
          </section>
        )}

        {historyAllowed && loading && (
          <p className="history-status">Loading your bills...</p>
        )}
        {historyAllowed && syncMessage && !loading && (
          <p className="auth-info">{syncMessage}</p>
        )}
        {historyAllowed && error && <p className="error-text">{error}</p>}

        {historyAllowed && !loading && !billId && !bills.length && !error && (
          <section className="history-empty">
            <p>No saved bills yet.</p>
            <Link to="/check" className="analyze-btn history-empty-cta">
              Check your first bill →
            </Link>
          </section>
        )}

        {historyAllowed && !loading && !billId && bills.length > 0 && (
          <ul className="history-list">
            {bills.map((bill) => {
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
                      {bill.report_kind === "prescription" ? (
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
                            Overcharged {formatCurrency(summary.totalOvercharged)}
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

        {historyAllowed && !loading && billId && selectedBill && (
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
              {selectedBill.report_kind === "prescription" &&
              !selectedBill.line_items?.length ? (
                <PrescriptionResults result={selectedBill} />
              ) : (
                <BillResults result={selectedBill} />
              )}
            </section>
          </>
        )}
      </main>
    </motion.div>
  );
}
