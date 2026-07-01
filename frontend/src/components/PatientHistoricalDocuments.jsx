import { useState } from "react";
import {
  DOCUMENT_TYPES,
  documentTypeLabel,
  guessDocumentType,
} from "../utils/documentBundle";
import DocumentFilePreview from "./DocumentFilePreview";
import { DEFAULT_FILE_ACCEPT, validateUploadFile } from "../utils/fileUpload";
import { detectDocumentDate, normalizeToIsoDate } from "../utils/documentDates";
import {
  buildExtractedSummary,
  deleteHistoricalDocument,
  extractHistoricalDocument,
  saveHistoricalDocument,
} from "../services/patientHistoricalDocuments";

export default function PatientHistoricalDocuments({
  userId,
  patientId,
  documents = [],
  onChange,
  disabled = false,
  embedded = false,
}) {
  const [file, setFile] = useState(null);
  const [documentType, setDocumentType] = useState("lab_report");
  const [suggestedType, setSuggestedType] = useState("lab_report");
  const [typeConfirmed, setTypeConfirmed] = useState(false);
  const [documentDate, setDocumentDate] = useState("");
  const [detectedDate, setDetectedDate] = useState("");
  const [extraction, setExtraction] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState(null);

  const resetUploadState = () => {
    setFile(null);
    setDocumentDate("");
    setDetectedDate("");
    setExtraction(null);
    setTypeConfirmed(false);
  };

  const handleFileChange = (event) => {
    const nextFile = event.target.files?.[0] || null;
    event.target.value = "";
    if (!nextFile) {
      return;
    }
    const validation = validateUploadFile(nextFile);
    if (!validation.ok) {
      setError(validation.error);
      return;
    }
    const guessed = guessDocumentType(nextFile.name);
    setFile(nextFile);
    setSuggestedType(guessed);
    setDocumentType(guessed);
    setTypeConfirmed(false);
    setDocumentDate("");
    setDetectedDate("");
    setExtraction(null);
    setError("");
  };

  const handleExtract = async () => {
    if (!file) {
      setError("Choose a document to upload.");
      return;
    }
    if (!typeConfirmed) {
      setError("Confirm the document type before extracting.");
      return;
    }

    setExtracting(true);
    setError("");
    try {
      const result = await extractHistoricalDocument(file, documentType);
      const foundDate = detectDocumentDate(documentType, result);
      setExtraction(result);
      setDetectedDate(foundDate);
      setDocumentDate(foundDate);
    } catch (err) {
      setExtraction(null);
      setDetectedDate("");
      setDocumentDate("");
      setError(err.message || "Unable to extract document.");
    } finally {
      setExtracting(false);
    }
  };

  const handleSave = async () => {
    if (!extraction) {
      setError("Extract the document before saving.");
      return;
    }
    if (!normalizeToIsoDate(documentDate)) {
      setError(
        detectedDate
          ? "Confirm or correct the document date before saving."
          : "We could not read a date from this document. Please enter the document date."
      );
      return;
    }

    setUploading(true);
    setError("");
    try {
      const extractedSummary = buildExtractedSummary(documentType, extraction);
      const saved = await saveHistoricalDocument(userId, patientId, {
        file,
        filename: file.name,
        documentType,
        documentDate: normalizeToIsoDate(documentDate),
        extractedSummary,
      });
      onChange?.([saved, ...documents]);
      resetUploadState();
    } catch (err) {
      setError(err.message || "Unable to save document.");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (doc) => {
    if (!window.confirm(`Delete historical document "${doc.filename}"?`)) {
      return;
    }
    setDeletingId(doc.id);
    setError("");
    try {
      await deleteHistoricalDocument(userId, patientId, doc.id);
      onChange?.(documents.filter((entry) => entry.id !== doc.id));
    } catch (err) {
      setError(err.message || "Unable to delete document.");
    } finally {
      setDeletingId(null);
    }
  };

  const HeadingTag = embedded ? "h3" : "h2";
  const busy = extracting || uploading;

  return (
    <section
      className={`patient-historical-docs${
        embedded ? " patient-historical-docs-embedded" : ""
      }`}
    >
      <HeadingTag>Historical documents</HeadingTag>
      <p className="clinical-history-hint">
        Upload older reports with the date they relate to. We read dates from
        documents when possible; otherwise you will be asked to enter them.
      </p>

      <div className="patient-historical-upload">
        <label className="setting-field setting-field-full">
          <span>Document file</span>
          <input
            type="file"
            accept={DEFAULT_FILE_ACCEPT}
            onChange={handleFileChange}
            disabled={disabled || busy}
          />
        </label>

        {file && (
          <div className="document-upload-preview-panel">
            <DocumentFilePreview file={file} />
            <div className="document-upload-preview-details">
              <p className="document-suggested-type">
                Suggested: {documentTypeLabel(suggestedType)}
              </p>
              <label className="setting-field setting-field-full">
                <span>Document type</span>
                <select
                  value={documentType}
                  onChange={(event) => {
                    setDocumentType(event.target.value);
                    setTypeConfirmed(false);
                    setExtraction(null);
                    setDetectedDate("");
                    setDocumentDate("");
                  }}
                  disabled={disabled || busy}
                >
                  {DOCUMENT_TYPES.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </label>
              {typeConfirmed ? (
                <span className="document-type-confirmed-badge">
                  ✓ Type confirmed
                </span>
              ) : (
                <button
                  type="button"
                  className="bill-editor-secondary document-type-confirm-btn"
                  onClick={() => setTypeConfirmed(true)}
                  disabled={disabled || busy}
                >
                  Confirm type
                </button>
              )}
            </div>
          </div>
        )}

        {file && typeConfirmed && !extraction && (
          <button
            type="button"
            className="analyze-btn"
            onClick={handleExtract}
            disabled={disabled || busy}
          >
            {extracting ? "Extracting..." : "Extract document"}
          </button>
        )}

        {extraction && (
          <>
            <label className="setting-field setting-field-full">
              <span>Document date</span>
              <input
                type="date"
                value={normalizeToIsoDate(documentDate)}
                onChange={(event) => setDocumentDate(event.target.value)}
                disabled={disabled || busy}
                required
              />
            </label>
            {detectedDate ? (
              <p className="auth-info">
                Date detected from the document. Confirm or correct it before
                saving.
              </p>
            ) : (
              <p className="clinical-history-hint">
                We could not read a date from this document. Please enter when
                it was issued.
              </p>
            )}
            <button
              type="button"
              className="analyze-btn"
              onClick={handleSave}
              disabled={disabled || busy || !normalizeToIsoDate(documentDate)}
            >
              {uploading ? "Saving..." : "Save to medical history"}
            </button>
          </>
        )}
      </div>

      {error && <p className="error-text">{error}</p>}

      <ul className="patient-historical-list">
        {documents.map((doc) => (
          <li
            key={doc.id}
            className={`patient-historical-item ${
              doc.typeConfirmed === false
                ? "document-bundle-item-unconfirmed"
                : "document-bundle-item-confirmed"
            }`}
          >
            <div>
              <strong>{doc.filename}</strong>
              <p>
                {documentTypeLabel(doc.documentType)} · {doc.documentDate}
              </p>
              {doc.extractedSummary?.diagnosis && (
                <p className="clinical-history-hint">
                  Diagnosis: {doc.extractedSummary.diagnosis}
                </p>
              )}
            </div>
            <button
              type="button"
              className="bill-editor-secondary"
              onClick={() => handleDelete(doc)}
              disabled={deletingId === doc.id}
            >
              {deletingId === doc.id ? "Deleting…" : "Delete"}
            </button>
          </li>
        ))}
      </ul>

      {!documents.length && (
        <p className="clinical-history-empty">No historical documents yet.</p>
      )}
    </section>
  );
}
