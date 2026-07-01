import { useCallback, useRef, useState } from "react";
import {
  allBundleDocumentsConfirmed,
  createBundleDocument,
  DOCUMENT_TYPES,
  documentTypeLabel,
} from "../utils/documentBundle";
import DocumentFilePreview from "./DocumentFilePreview";
import { DEFAULT_FILE_ACCEPT, validateUploadFile } from "../utils/fileUpload";

export default function MultiDocumentUpload({
  documents = [],
  onChange,
  onValidationError,
  disabled = false,
  className = "",
  showTypeConfirmBanner = true,
}) {
  const inputRef = useRef(null);
  const dragCounterRef = useRef(0);
  const [isDragging, setIsDragging] = useState(false);

  const hasUnconfirmed = documents.length > 0 && !allBundleDocumentsConfirmed(documents);

  const addFiles = useCallback(
    (fileList) => {
      const files = Array.from(fileList || []);
      if (!files.length) {
        return;
      }

      const next = [...documents];
      const errors = [];

      for (const file of files) {
        const validation = validateUploadFile(file);
        if (!validation.ok) {
          errors.push(`${file.name}: ${validation.error}`);
          continue;
        }
        next.push(createBundleDocument(file));
      }

      if (errors.length) {
        onValidationError?.(errors.join(" "));
      } else {
        onValidationError?.("");
      }

      if (next.length !== documents.length) {
        onChange(next);
      }
    },
    [documents, onChange, onValidationError]
  );

  const handleDragEnter = (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (disabled) {
      return;
    }
    dragCounterRef.current += 1;
    setIsDragging(true);
  };

  const handleDragLeave = (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (disabled) {
      return;
    }
    dragCounterRef.current -= 1;
    if (dragCounterRef.current <= 0) {
      dragCounterRef.current = 0;
      setIsDragging(false);
    }
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    event.stopPropagation();
  };

  const handleDrop = (event) => {
    event.preventDefault();
    event.stopPropagation();
    dragCounterRef.current = 0;
    setIsDragging(false);
    if (disabled) {
      return;
    }
    addFiles(event.dataTransfer.files);
  };

  const handleInputChange = (event) => {
    addFiles(event.target.files);
    event.target.value = "";
  };

  const removeDocument = (id) => {
    onChange(documents.filter((doc) => doc.id !== id));
  };

  const updateDocumentType = (id, documentType) => {
    onChange(
      documents.map((doc) =>
        doc.id === id
          ? { ...doc, documentType, typeConfirmed: false }
          : doc
      )
    );
  };

  const confirmDocumentType = (id) => {
    onChange(
      documents.map((doc) =>
        doc.id === id ? { ...doc, typeConfirmed: true } : doc
      )
    );
  };

  return (
    <div className={`multi-document-upload ${className}`.trim()}>
      <button
        type="button"
        className={`upload-zone ${isDragging ? "upload-zone-dragging" : ""}`}
        onClick={() => !disabled && inputRef.current?.click()}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        disabled={disabled}
        aria-label="Add medical documents"
      >
        <div className="upload-icon">+</div>
        <p className="upload-title">
          {isDragging
            ? "Drop your documents here"
            : "Add bills, prescriptions, lab reports, and more"}
        </p>
        <p className="upload-subtitle">
          Drop multiple files or click to browse · PDF, JPG, PNG
        </p>
      </button>

      <input
        ref={inputRef}
        className="hidden-input"
        type="file"
        accept={DEFAULT_FILE_ACCEPT}
        multiple
        onChange={handleInputChange}
        disabled={disabled}
      />

      {showTypeConfirmBanner && hasUnconfirmed && (
        <p className="document-type-confirm-banner" role="status">
          Confirm the type for every document before analyzing.
        </p>
      )}

      {documents.length > 0 && (
        <ul className="document-bundle-list">
          {documents.map((doc) => (
            <li
              key={doc.id}
              className={`document-bundle-item ${
                doc.typeConfirmed
                  ? "document-bundle-item-confirmed"
                  : "document-bundle-item-unconfirmed"
              }`}
            >
              <div className="document-bundle-item-body">
                <DocumentFilePreview file={doc.file} />
                <div className="document-bundle-item-content">
                  <div className="document-bundle-item-header">
                    <span className="file-name">{doc.file?.name}</span>
                    <button
                      type="button"
                      className="bill-editor-secondary document-bundle-remove"
                      onClick={() => removeDocument(doc.id)}
                      disabled={disabled}
                      aria-label={`Remove ${doc.file?.name}`}
                    >
                      Remove
                    </button>
                  </div>
                  <div className="document-bundle-item-main">
                    <p className="document-suggested-type">
                      Suggested:{" "}
                      {documentTypeLabel(doc.suggestedType || doc.documentType)}
                    </p>
                    <div className="document-type-row">
                      <select
                        className="document-type-select"
                        value={doc.documentType}
                        onChange={(event) =>
                          updateDocumentType(doc.id, event.target.value)
                        }
                        disabled={disabled}
                        aria-label={`Document type for ${doc.file?.name}`}
                      >
                        {DOCUMENT_TYPES.map((type) => (
                          <option key={type.id} value={type.id}>
                            {type.label}
                          </option>
                        ))}
                      </select>
                      {doc.typeConfirmed ? (
                        <span
                          className="document-type-confirmed-badge"
                          aria-label="Type confirmed"
                        >
                          ✓ Confirmed
                        </span>
                      ) : (
                        <button
                          type="button"
                          className="bill-editor-secondary document-type-confirm-btn"
                          onClick={() => confirmDocumentType(doc.id)}
                          disabled={disabled}
                        >
                          Confirm type
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
