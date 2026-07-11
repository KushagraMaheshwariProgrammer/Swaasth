import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  buildMedicalHistoryDossier,
  buildMedicalHistoryFilename,
} from "../utils/buildMedicalHistoryDossier";
import {
  downloadReportPdf,
  loadReportPdfBlobUrl,
  revokeReportPdfBlobUrl,
  shareReportPdf,
} from "../services/reportPdf";
import { canSaveMedicalHistory } from "../utils/medicalHistoryConsent";
import ReportPdfViewer from "./ReportPdfViewer";

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
  const [viewer, setViewer] = useState(null);
  const [busyAction, setBusyAction] = useState("");
  const pdfCacheRef = useRef({ blob: null, blobUrl: "", filename: "", title: "" });

  const consentAllows = canSaveMedicalHistory(accountConsent, patient);

  useEffect(() => {
    return () => {
      revokeReportPdfBlobUrl(pdfCacheRef.current.blobUrl);
      pdfCacheRef.current = { blob: null, blobUrl: "", filename: "", title: "" };
    };
  }, [patient?.id]);

  const ensurePdf = async (dossier) => {
    if (pdfCacheRef.current.blob) {
      return pdfCacheRef.current;
    }
    const loaded = await loadReportPdfBlobUrl(dossier);
    pdfCacheRef.current = loaded;
    return loaded;
  };

  const openViewer = (loaded) => {
    setViewer({
      blobUrl: loaded.blobUrl,
      title: loaded.title || "Medical History Summary",
    });
  };

  const handleExport = async (mode) => {
    if (!consentAllows) {
      setError("Enable medical history consent for your account and this patient first.");
      return;
    }

    setExporting(true);
    setBusyAction(mode);
    setError("");
    setInfo("");
    try {
      const dossier = await buildMedicalHistoryDossier(userId, patient, {
        accountConsent,
        includeSwaasthReports,
      });
      const filename = buildMedicalHistoryFilename(dossier);
      const loaded = await ensurePdf(dossier);

      if (mode === "share") {
        const outcome = await shareReportPdf(dossier, loaded.blob);
        if (outcome.cancelled) {
          return;
        }
        if (outcome.shared) {
          setInfo("Medical history PDF shared.");
          return;
        }
        if (outcome.needsPreview) {
          openViewer(loaded);
          setInfo("Sharing isn't supported here — opened the PDF preview instead.");
          return;
        }
      }

      const outcome = await downloadReportPdf(dossier, filename, loaded.blob);
      if (outcome.path) {
        setInfo(`Medical history PDF saved to ${outcome.path}.`);
        return;
      }
      setInfo("Medical history PDF downloaded.");
    } catch (err) {
      setError(err.message || "Could not export medical history.");
    } finally {
      setExporting(false);
      setBusyAction("");
    }
  };

  const handleViewerDownload = () => handleExport("download");
  const handleViewerShare = () => handleExport("share");

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

      {viewer && (
        <ReportPdfViewer
          blobUrl={viewer.blobUrl}
          title={viewer.title}
          onClose={() => setViewer(null)}
          onDownload={handleViewerDownload}
          onShare={handleViewerShare}
          busyAction={busyAction}
        />
      )}
    </section>
  );
}
