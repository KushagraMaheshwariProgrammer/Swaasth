import { useEffect } from "react";
import { DOCUMENT_TYPES, documentTypeLabel } from "../utils/documentBundle";
import DocumentFilePreview from "./DocumentFilePreview";

export default function DocumentTypeDetailView({
  document: bundleDocument,
  onClose,
  onUpdateType,
  onConfirm,
  disabled = false,
}) {
  useEffect(() => {
    const previousOverflow = window.document.body.style.overflow;
    window.document.body.style.overflow = "hidden";
    return () => {
      window.document.body.style.overflow = previousOverflow;
    };
  }, []);

  if (!bundleDocument) {
    return null;
  }

  const showConfirmButton = !bundleDocument.typeConfirmed;
  const isAutoClassified =
    bundleDocument.autoClassified && bundleDocument.typeConfirmed;

  return (
    <div
      className="document-type-detail-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={`Review ${bundleDocument.file?.name}`}
    >
      <div className="document-type-detail-card">
        <div className="document-type-detail-header">
          <button
            type="button"
            className="bill-editor-secondary document-type-detail-back"
            onClick={onClose}
          >
            ← Back
          </button>
          <span className="document-type-detail-filename">
            {bundleDocument.file?.name}
          </span>
        </div>

        <div className="document-type-detail-preview">
          <DocumentFilePreview
            file={bundleDocument.file}
            className="document-type-detail-preview-media"
          />
        </div>

        <div
          className={`document-type-detail-controls ${
            isAutoClassified ? "document-type-detail-controls-auto" : ""
          } ${showConfirmButton ? "document-type-detail-controls-unconfirmed" : ""}`}
        >
          {bundleDocument.classifying && (
            <p className="document-classifying-status" role="status">
              Classifying document… you can choose or confirm the type below while
              this runs.
            </p>
          )}
          {isAutoClassified && (
            <p className="document-auto-classified-note">
              Classified by the system as{" "}
              <strong>{documentTypeLabel(bundleDocument.documentType)}</strong>.
              You can change it below if needed.
            </p>
          )}
          {showConfirmButton && (
            <p className="document-needs-confirmation-note">
              {bundleDocument.classifying
                ? "Choose the document type below, or wait for the system suggestion."
                : "The system is unsure about this document. Please confirm or change the type."}
            </p>
          )}
          <label className="setting-field setting-field-full">
            <span>Document type</span>
            <select
              className="document-type-select document-type-select-detail"
              value={bundleDocument.documentType}
              onChange={(event) =>
                onUpdateType(bundleDocument.id, event.target.value)
              }
              disabled={disabled}
            >
              {DOCUMENT_TYPES.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.label}
                </option>
              ))}
            </select>
          </label>
          {bundleDocument.typeConfirmed ? (
            <span
              className={`document-type-confirmed-badge ${
                isAutoClassified ? "document-type-auto-badge" : ""
              }`}
            >
              {isAutoClassified ? "✓ Classified by system" : "✓ Confirmed"}
            </span>
          ) : (
            <button
              type="button"
              className="analyze-btn document-type-detail-confirm"
              onClick={() => onConfirm(bundleDocument.id)}
              disabled={disabled}
            >
              Confirm type
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
