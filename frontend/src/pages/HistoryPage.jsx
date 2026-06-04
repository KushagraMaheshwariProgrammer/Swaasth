import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import BillResults from "../components/BillResults";
import { computeBillSummary, formatCurrency } from "../billUtils";
import { useAuth } from "../context/AuthContext";
import { getBill, getBillSortTime, getUserBills } from "../services/bills";

const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.35 },
};

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
  const { user } = useAuth();
  const navigate = useNavigate();
  const [bills, setBills] = useState([]);
  const [selectedBill, setSelectedBill] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncMessage, setSyncMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      if (!user) {
        return;
      }
      setLoading(true);
      setError("");
      setSyncMessage("");
      try {
        if (billId) {
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
          const entries = await getUserBills(user.uid);
          if (cancelled) {
            return;
          }
          const pendingLocal = entries.filter((bill) => bill.localOnly).length;
          if (pendingLocal > 0) {
            setSyncMessage(
              `${pendingLocal} bill${pendingLocal === 1 ? "" : "s"} saved on this device — will sync when online.`
            );
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
              : "Every compared bill is saved to your account automatically."}
          </p>
        </header>

        {loading && <p className="history-status">Loading your bills...</p>}
        {syncMessage && !loading && <p className="auth-info">{syncMessage}</p>}
        {error && <p className="error-text">{error}</p>}

        {!loading && !billId && !bills.length && !error && (
          <section className="history-empty">
            <p>No saved bills yet.</p>
            <Link to="/check" className="analyze-btn history-empty-cta">
              Check your first bill →
            </Link>
          </section>
        )}

        {!loading && !billId && bills.length > 0 && (
          <ul className="history-list">
            {bills.map((bill) => {
              const summary = computeBillSummary(bill);
              const title =
                bill.hospital?.name_from_bill ||
                bill.filename ||
                "Hospital bill";
              return (
                <li key={bill.id}>
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
                      {bill.comparison_settings?.city &&
                      bill.comparison_settings?.state_name
                        ? `${bill.comparison_settings.city}, ${bill.comparison_settings.state_name}`
                        : "Location not recorded"}
                      {" · "}
                      {bill.line_items?.length || 0} items
                    </p>
                    <div className="history-card-stats">
                      <span>Charged {formatCurrency(summary.totalCharged)}</span>
                      <span className="history-overcharge">
                        Overcharged {formatCurrency(summary.totalOvercharged)}
                      </span>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        {!loading && billId && selectedBill && (
          <section className="results-shell">
            <BillResults result={selectedBill} />
          </section>
        )}
      </main>
    </motion.div>
  );
}
