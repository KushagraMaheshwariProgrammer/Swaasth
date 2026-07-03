import { useState } from "react";
import { documentTypeLabel } from "../utils/documentBundle";
import DocumentExtractedDataEditor from "./DocumentExtractedDataEditor";
import DocumentFilePreview from "./DocumentFilePreview";

export default function BundleExtractionReview({
  documents = [],
  onChange,
  onContinue,
  onBack,
  disabled = false,
  error = "",
  extractionWarnings = [],
}) {
  const [expandedId, setExpandedId] = useState(documents[0]?.id || null);

  const updateDocument = (docId, patch) => {
    onChange(
      documents.map((doc) => (doc.id === docId ? { ...doc, ...patch } : doc))
    );
  };

  const updateEditable = (docId, editableExtraction) => {
    updateDocument(docId, { editableExtraction });
  };

  const toggleExpanded = (docId) => {
    setExpandedId((current) => (current === docId ? null : docId));
  };

  const docsWithExtraction = documents.filter((doc) => doc.editableExtraction);
  const docsWithErrors = documents.filter((doc) => doc.extractionError);

  return (
    <section className="bill-editor-shell bundle-extraction-review">
      <header className="bill-editor-header">
        <div>
          <h2>Review extracted data</h2>
          <p>
            We read each document after OCR. Check the extracted fields, then add,
            remove, or correct anything before analysis.
          </p>
        </div>
        <span className="bill-editor-count">
          {documents.length} document{documents.length === 1 ? "" : "s"}
        </span>
      </header>

      {extractionWarnings.length > 0 && (
        <div className="extraction-warnings-panel" role="status">
          <p className="clinical-history-hint">
            Some documents could not be read automatically:
          </p>
          <ul className="extraction-warnings-list">
            {extractionWarnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      <ul className="bundle-extraction-list">
        {documents.map((doc) => {
          const isExpanded = expandedId === doc.id;
          const hasData = Boolean(doc.editableExtraction);
          const hasError = Boolean(doc.extractionError);

          return (
            <li
              key={doc.id}
              className={`bundle-extraction-item ${
                isExpanded ? "bundle-extraction-item-expanded" : ""
              } ${hasError ? "bundle-extraction-item-error" : ""}`}
            >
              <button
                type="button"
                className="bundle-extraction-item-header"
                onClick={() => toggleExpanded(doc.id)}
                aria-expanded={isExpanded}
              >
                <DocumentFilePreview
                  file={doc.file}
                  className="bundle-extraction-preview"
                  ariaLabel={`Preview ${doc.file?.name}`}
                />
                <div className="bundle-extraction-item-summary">
                  <strong>{doc.file?.name}</strong>
                  <p>{documentTypeLabel(doc.documentType)}</p>
                  {hasError && (
                    <p className="error-text bundle-extraction-error">
                      {doc.extractionError}
                    </p>
                  )}
                  {hasData && !hasError && (
                    <p className="auth-info">Tap to review or edit extracted data</p>
                  )}
                </div>
                <span className="bundle-extraction-chevron" aria-hidden="true">
                  {isExpanded ? "▾" : "▸"}
                </span>
              </button>

              {isExpanded && hasData && (
                <div className="bundle-extraction-item-body">
                  <DocumentExtractedDataEditor
                    editable={doc.editableExtraction}
                    onChange={(editableExtraction) =>
                      updateEditable(doc.id, editableExtraction)
                    }
                    disabled={disabled}
                  />
                </div>
              )}

              {isExpanded && hasError && !hasData && (
                <div className="bundle-extraction-item-body">
                  <p className="clinical-history-hint">
                    This document could not be extracted. Remove it and try a
                    clearer scan, or change the document type and extract again.
                  </p>
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {docsWithExtraction.length === 0 && (
        <p className="error-text">
          No documents were extracted successfully. Check your files and try again.
        </p>
      )}

      {error && <p className="error-text">{error}</p>}

      <div className="bill-editor-actions">
        {onBack && (
          <button
            type="button"
            className="bill-editor-secondary"
            onClick={onBack}
            disabled={disabled}
          >
            Back to upload
          </button>
        )}
        <button
          type="button"
          className="analyze-btn bill-editor-primary"
          onClick={onContinue}
          disabled={disabled || docsWithExtraction.length === 0}
        >
          Continue to analysis
        </button>
      </div>

      {docsWithErrors.length > 0 && docsWithExtraction.length > 0 && (
        <p className="clinical-history-hint">
          Documents with extraction errors will be skipped during analysis unless
          you remove them or re-upload.
        </p>
      )}
    </section>
  );
}
