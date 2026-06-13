import { useState } from "react";
import { formatCurrency } from "../billUtils";
import {
  downloadReportPdf,
  openReportPdf,
  shareReportPdf,
} from "../services/aarogyaBhadratha";

const STATUS_META = {
  "Above Approved Rate": { cls: "status-pill status-red", card: "abh-item-card abh-item-above" },
  "Within Approved Rate": { cls: "status-pill status-green", card: "abh-item-card abh-item-ok" },
  "Below Approved Rate": { cls: "status-pill status-green", card: "abh-item-card abh-item-ok" },
  "Manual Verification Required": {
    cls: "status-pill status-amber",
    card: "abh-item-card abh-item-manual",
  },
  "Rate Not Found": { cls: "status-pill status-neutral", card: "abh-item-card abh-item-unverified" },
};

function statusMeta(status) {
  return STATUS_META[status] || STATUS_META["Rate Not Found"];
}

function confidenceLabel(value) {
  if (!value && value !== 0) {
    return "—";
  }
  return `${Math.round(Number(value) * 100)}%`;
}

export default function AarogyaResults({ report, toolbar = null }) {
  const [pdfMessage, setPdfMessage] = useState("");
  const [busy, setBusy] = useState("");

  if (!report?.comparison?.items) {
    return null;
  }

  const patient = report.patient || {};
  const hospital = report.hospital || {};
  const matched = hospital.matched_hospital || {};
  const bill = report.bill || {};
  const summary = report.comparison.summary || {};
  const items = report.comparison.items || [];

  const handleView = async () => {
    setBusy("view");
    setPdfMessage("");
    try {
      await openReportPdf(report);
    } catch {
      setPdfMessage("Could not open the report. Check your connection and try again.");
    } finally {
      setBusy("");
    }
  };

  const handleDownload = async () => {
    setBusy("download");
    setPdfMessage("");
    try {
      await downloadReportPdf(
        report,
        `aarogya-bhadratha-${(patient.name || "report").replace(/\s+/g, "-")}.pdf`
      );
    } catch {
      setPdfMessage("Could not download the report. Check your connection and try again.");
    } finally {
      setBusy("");
    }
  };

  const handleShare = async () => {
    setBusy("share");
    setPdfMessage("");
    try {
      const shared = await shareReportPdf(report);
      if (!shared) {
        setPdfMessage("Sharing isn't supported here — opened the report instead.");
      }
    } catch {
      setPdfMessage("Could not share the report.");
    } finally {
      setBusy("");
    }
  };

  const specialities = matched.specialities?.length
    ? matched.specialities.join(", ")
    : matched.specialities_text || "—";

  return (
    <div className="abh-report">
      <header className="abh-report-header">
        <h2>Aarogya Bhadratha Rate Comparison</h2>
        <p className="abh-empanel-badge">
          This hospital is empanelled under the Aarogya Bhadratha Scheme.
        </p>
      </header>

      {toolbar && <div className="results-toolbar">{toolbar}</div>}

      <section className="abh-info-card">
        <div className="abh-info-grid">
          <div>
            <span className="abh-info-label">Patient</span>
            <strong>{patient.name || "—"}</strong>
          </div>
          <div>
            <span className="abh-info-label">Hospital (from bill / OCR)</span>
            <strong>{hospital.ocr_hospital_name || "—"}</strong>
          </div>
          <div>
            <span className="abh-info-label">Matched empanelled hospital</span>
            <strong>{matched.name || "—"}</strong>
          </div>
          <div>
            <span className="abh-info-label">District</span>
            <strong>{matched.district || "—"}</strong>
          </div>
          <div className="abh-info-wide">
            <span className="abh-info-label">Address</span>
            <strong>{matched.address || "—"}</strong>
          </div>
          <div className="abh-info-wide">
            <span className="abh-info-label">Speciality</span>
            <strong>{specialities}</strong>
          </div>
          <div>
            <span className="abh-info-label">Hospital code</span>
            <strong>{matched.hospital_code || `Ref ${matched.ref_no || "—"}`}</strong>
          </div>
          <div>
            <span className="abh-info-label">Bill date</span>
            <strong>{bill.bill_date || "—"}</strong>
          </div>
          <div>
            <span className="abh-info-label">Empanelment status</span>
            <strong className="abh-status-empanelled">Empanelled</strong>
          </div>
          <div>
            <span className="abh-info-label">Match confidence</span>
            <strong>
              {confidenceLabel(hospital.match_confidence)} ({hospital.match_method || "—"})
            </strong>
          </div>
          <div>
            <span className="abh-info-label">Original bill total</span>
            <strong>{formatCurrency(bill.original_total)}</strong>
          </div>
        </div>
      </section>

      <article className="summary-banner abh-summary">
        <div className="summary-stat">
          <p>Total Charged</p>
          <h3>{formatCurrency(summary.total_charged)}</h3>
        </div>
        <div className="summary-stat">
          <p>Approved (matched)</p>
          <h3>{formatCurrency(summary.total_approved_matched)}</h3>
        </div>
        <div className="summary-stat summary-focus">
          <p>Possible Excess</p>
          <h3>{formatCurrency(summary.total_possible_excess)}</h3>
        </div>
      </article>

      <p className="abh-matched-note">
        The approved total only includes items that were reliably matched with
        the Aarogya Bhadratha rates database.
      </p>

      <div className="abh-summary-chips">
        <span>{summary.matched_items ?? 0} matched</span>
        <span>{summary.unmatched_items ?? 0} unmatched</span>
        <span>{summary.manual_verification_items ?? 0} need verification</span>
        {summary.percentage_difference != null && (
          <span>{summary.percentage_difference}% vs approved</span>
        )}
        {summary.total_below_approved > 0 && (
          <span>{formatCurrency(summary.total_below_approved)} below approved</span>
        )}
      </div>

      <div className="abh-item-list">
        {items.map((item, index) => {
          const meta = statusMeta(item.status);
          return (
            <article key={`${item.item_name || "item"}-${index}`} className={meta.card}>
              <div className="abh-item-top">
                <h4>{item.item_name || "—"}</h4>
                <span className={meta.cls}>{item.status}</span>
              </div>
              {item.matched_name ? (
                <p className="matched-reference">
                  Matched: {item.matched_name}
                  {item.matched_code ? ` (${item.matched_code})` : ""}
                  {item.match_confidence
                    ? ` · ${confidenceLabel(item.match_confidence)} ${item.match_method || ""}`
                    : ""}
                </p>
              ) : (
                <p className="matched-reference abh-unverified-note">
                  {item.note || "Rate not found in the Aarogya Bhadratha rates database."}
                </p>
              )}
              <div className="result-metrics">
                <div>
                  <p>Qty</p>
                  <h5>{item.quantity}</h5>
                </div>
                <div>
                  <p>Charged</p>
                  <h5>{formatCurrency(item.total_price)}</h5>
                </div>
                <div>
                  <p>Approved</p>
                  <h5>{formatCurrency(item.approved_amount)}</h5>
                </div>
                <div>
                  <p>Excess</p>
                  <h5>{formatCurrency(item.excess_amount)}</h5>
                </div>
              </div>
              {item.status === "Manual Verification Required" && item.note && (
                <p className="abh-manual-note">{item.note}</p>
              )}
            </article>
          );
        })}
      </div>

      <p className="abh-disclaimer">{report.disclaimer}</p>

      <div className="abh-report-actions">
        <button
          type="button"
          className="bill-editor-secondary"
          onClick={handleView}
          disabled={busy === "view"}
        >
          {busy === "view" ? "Opening…" : "View Full Report"}
        </button>
        <button
          type="button"
          className="bill-editor-secondary"
          onClick={handleDownload}
          disabled={busy === "download"}
        >
          {busy === "download" ? "Preparing…" : "Download Report"}
        </button>
        <button
          type="button"
          className="analyze-btn abh-share-btn"
          onClick={handleShare}
          disabled={busy === "share"}
        >
          {busy === "share" ? "Sharing…" : "Share Report"}
        </button>
      </div>
      {pdfMessage && <p className="auth-info">{pdfMessage}</p>}
    </div>
  );
}
