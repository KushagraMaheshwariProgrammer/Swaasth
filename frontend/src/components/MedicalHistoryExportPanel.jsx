import { useState } from "react";
import { Link } from "react-router-dom";
import {
  buildMedicalHistoryDossier,
  buildMedicalHistoryFilename,
} from "../utils/buildMedicalHistoryDossier";
import {
  downloadReportPdf,
  shareReportPdf,
} from "../services/reportPdf";
import { canSaveMedicalHistory } from "../utils/medicalHistoryConsent";

export default function MedicalHistoryExportPanel({
  userId,
  patient,
  accountConsent,
  disabled = false,
}) {
  const [includeSwaasthReports, setIncludeSwaasthReports] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const consentAllows = canSaveMedicalHistory(accountConsent, patient);

  const handleExport = async (mode) => {
    if (!consentAllows) {
      setError("Enable medical history consent for your account and this patient first.");
      return;
    }

    setExporting(true);
    setError("");
    setInfo("");
    try {
      const dossier = await buildMedicalHistoryDossier(userId, patient, {
        accountConsent,
        includeSwaasthReports,
      });
      const filename = buildMedicalHistoryFilename(dossier);

      if (mode === "share") {
        const outcome = await shareReportPdf(dossier);
        if (outcome.cancelled) {
          return;
        }
        if (outcome.shared) {
          setInfo("Medical history PDF shared.");
          return;
        }
      }

      const outcome = await downloadReportPdf(dossier, filename);
      if (outcome.method === "cancelled") {
        return;
      }
      setInfo(
        outcome.method === "share"
          ? "Medical history PDF shared."
          : "Medical history PDF downloaded."
      );
    } catch (err) {
      setError(err.message || "Could not export medical history.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <section className="medical-history-export-panel">
      <h3>Compile & share medical history</h3>
      <p className="clinical-history-hint">
        Create a single PDF of this patient&apos;s medical history from profile
        data, uploaded documents, and optionally Swaasth analysis reports.
      </p>

      {!consentAllows ? (
        <div>
          <p className="clinical-history-hint">
            Medical history export requires your account consent and patient
            opt-in to saving history.
          </p>
          <Link to="/consent/medical-history" className="patients-manage-link">
            Manage medical history consent
          </Link>
        </div>
      ) : (
        <>
          <label className="setting-field setting-field-full medical-history-export-toggle">
            <input
              type="checkbox"
              checked={includeSwaasthReports}
              onChange={(event) => setIncludeSwaasthReports(event.target.checked)}
              disabled={disabled || exporting}
            />
            <span>Include Swaasth analysis reports</span>
          </label>

          <div className="medical-history-export-actions">
            <button
              type="button"
              className="analyze-btn"
              onClick={() => handleExport("download")}
              disabled={disabled || exporting}
            >
              {exporting ? "Preparing PDF..." : "Download PDF"}
            </button>
            <button
              type="button"
              className="bill-editor-secondary"
              onClick={() => handleExport("share")}
              disabled={disabled || exporting}
            >
              Share PDF
            </button>
          </div>
        </>
      )}

      {info && <p className="auth-info">{info}</p>}
      {error && <p className="error-text">{error}</p>}
    </section>
  );
}
