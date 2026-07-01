import { useState } from "react";
import {
  DOCUMENT_TYPES,
  documentTypeLabel,
  guessDocumentType,
} from "../utils/documentBundle";
import { DEFAULT_FILE_ACCEPT, validateUploadFile } from "../utils/fileUpload";
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
}) {
  const [file, setFile] = useState(null);
  const [documentType, setDocumentType] = useState("lab_report");
  const [suggestedType, setSuggestedType] = useState("lab_report");
  const [typeConfirmed, setTypeConfirmed] = useState(false);
  const [documentDate, setDocumentDate] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState(null);

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
    setError("");
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Choose a document to upload.");
      return;
    }
    if (!typeConfirmed) {
      setError("Confirm the document type before uploading.");
      return;
    }
    if (!documentDate) {
      setError("Enter the document date.");
      return;
    }

    setUploading(true);
    setError("");
    try {
      const extraction = await extractHistoricalDocument(file, documentType);
      const extractedSummary = buildExtractedSummary(documentType, extraction);
      const saved = await saveHistoricalDocument(userId, patientId, {
        file,
        filename: file.name,
        documentType,
        documentDate,
        extractedSummary,
      });
      onChange?.([saved, ...documents]);
      setFile(null);
      setDocumentDate("");
      setTypeConfirmed(false);
    } catch (err) {
      setError(err.message || "Unable to upload document.");
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

  return (
    <section className="patient-historical-docs">
      <h2>Historical documents</h2>
      <p className="clinical-history-hint">
        Upload older reports with the date they relate to. Confirm the document
        type before extracting.
      </p>

      <div className="patient-historical-upload">
        <label className="setting-field setting-field-full">
          <span>Document file</span>
          <input
            type="file"
            accept={DEFAULT_FILE_ACCEPT}
            onChange={handleFileChange}
            disabled={disabled || uploading}
          />
        </label>

        {file && (
          <>
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
                }}
                disabled={disabled || uploading}
              >
                {DOCUMENT_TYPES.map((type) => (
                  <option key={type.id} value={type.id}>
                    {type.label}
                  </option>
                ))}
              </select>
            </label>
            {typeConfirmed ? (
              <span className="document-type-confirmed-badge">✓ Type confirmed</span>
            ) : (
              <button
                type="button"
                className="bill-editor-secondary document-type-confirm-btn"
                onClick={() => setTypeConfirmed(true)}
                disabled={disabled || uploading}
              >
                Confirm type
              </button>
            )}
          </>
        )}

        <label className="setting-field setting-field-full">
          <span>Document date</span>
          <input
            type="date"
            value={documentDate}
            onChange={(event) => setDocumentDate(event.target.value)}
            disabled={disabled || uploading}
            required
          />
        </label>

        <button
          type="button"
          className="analyze-btn"
          onClick={handleUpload}
          disabled={disabled || uploading || !file || !typeConfirmed || !documentDate}
        >
          {uploading ? "Uploading & extracting..." : "Upload & extract"}
        </button>
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
