import { useState } from "react";
import { canExportReport, buildReportFilename } from "../data/schemes";
import {
  downloadReportPdf,
  openReportPdf,
  shareReportPdf,
} from "../services/reportPdf";

export default function ReportActions({ report, className = "report-actions" }) {
  const [pdfMessage, setPdfMessage] = useState("");
  const [busy, setBusy] = useState("");

  if (!canExportReport(report)) {
    return null;
  }

  const filename = buildReportFilename(report);

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
      await downloadReportPdf(report, filename);
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

  return (
    <>
      <div className={className}>
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
          className="analyze-btn report-share-btn"
          onClick={handleShare}
          disabled={busy === "share"}
        >
          {busy === "share" ? "Sharing…" : "Share Report"}
        </button>
      </div>
      {pdfMessage && <p className="auth-info">{pdfMessage}</p>}
    </>
  );
}
