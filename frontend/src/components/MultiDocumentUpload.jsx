import { useCallback, useEffect, useRef, useState } from "react";
import {
  applyDocumentClassification,
  bundleHasClassifyingDocuments,
  createBundleDocument,
  DOCUMENT_TYPES,
  documentTypeLabel,
  documentsNeedingConfirmation,
} from "../utils/documentBundle";
import DocumentFilePreview from "./DocumentFilePreview";
import DocumentTypeDetailView from "./DocumentTypeDetailView";
import { DEFAULT_FILE_ACCEPT, validateUploadFile } from "../utils/fileUpload";
import { classifyDocument } from "../services/prescriptions";

function DocumentTypeControls({
  doc,
  disabled,
  onUpdateType,
  onConfirm,
}) {
  const isAutoClassified = doc.autoClassified && doc.typeConfirmed;

  return (
    <>
      {doc.classifying && (
        <p className="document-classifying-status" role="status">
          Classifying… you can choose or confirm the type below while we check.
        </p>
      )}
      {isAutoClassified ? (
        <p className="document-auto-classified-note">
          Classified by the system as{" "}
          <strong>{documentTypeLabel(doc.documentType)}</strong>
        </p>
      ) : doc.typeConfirmed ? (
        <p className="document-suggested-type">
          Type: {documentTypeLabel(doc.documentType)}
        </p>
      ) : (
        <p className="document-needs-confirmation-note">
          Please confirm: suggested{" "}
          {documentTypeLabel(doc.suggestedType || doc.documentType)}
        </p>
      )}
      <div className="document-type-row">
        <select
          className={`document-type-select ${
            isAutoClassified ? "document-type-select-auto" : ""
          }`}
          value={doc.documentType}
          onChange={(event) => onUpdateType(doc.id, event.target.value)}
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
            className={`document-type-confirmed-badge ${
              isAutoClassified ? "document-type-auto-badge" : ""
            }`}
            aria-label={isAutoClassified ? "Classified by system" : "Type confirmed"}
          >
            {isAutoClassified ? "✓ Classified by system" : "✓ Confirmed"}
          </span>
        ) : (
          <button
            type="button"
            className="bill-editor-secondary document-type-confirm-btn"
            onClick={() => onConfirm(doc.id)}
            disabled={disabled}
          >
            Confirm type
          </button>
        )}
      </div>
    </>
  );
}

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
  const documentsRef = useRef(documents);
  const scrollRestoreRef = useRef(0);
  const [isDragging, setIsDragging] = useState(false);
  const [activeDocId, setActiveDocId] = useState(null);

  useEffect(() => {
    documentsRef.current = documents;
  }, [documents]);

  const needsConfirmation = documentsNeedingConfirmation(documents);
  const hasUnconfirmed = needsConfirmation.length > 0;
  const isClassifying = bundleHasClassifyingDocuments(documents);
  const activeDocument = documents.find((doc) => doc.id === activeDocId) || null;

  const classifyDocumentById = useCallback(
    async (docId, file) => {
      try {
        const result = await classifyDocument(file);
        onChange(
          documentsRef.current.map((doc) => {
            if (doc.id !== docId) {
              return doc;
            }
            if (doc.typeConfirmed && !doc.autoClassified) {
              return {
                ...doc,
                classifying: false,
                classificationConfidence: result?.confidence || doc.classificationConfidence,
              };
            }
            return applyDocumentClassification(doc, result);
          })
        );
      } catch {
        onChange(
          documentsRef.current.map((doc) =>
            doc.id === docId
              ? {
                  ...doc,
                  classifying: false,
                  classificationConfidence: "low",
                  autoClassified: false,
                  typeConfirmed:
                    doc.typeConfirmed && !doc.autoClassified ? doc.typeConfirmed : false,
                }
              : doc
          )
        );
      }
    },
    [onChange]
  );

  const addFiles = useCallback(
    (fileList) => {
      const files = Array.from(fileList || []);
      if (!files.length) {
        return;
      }

      const next = [...documents];
      const errors = [];
      const addedDocs = [];

      for (const file of files) {
        const validation = validateUploadFile(file);
        if (!validation.ok) {
          errors.push(`${file.name}: ${validation.error}`);
          continue;
        }
        const doc = createBundleDocument(file);
        next.push(doc);
        addedDocs.push(doc);
      }

      if (errors.length) {
        onValidationError?.(errors.join(" "));
      } else {
        onValidationError?.("");
      }

      if (addedDocs.length) {
        onChange(next);
        for (const doc of addedDocs) {
          classifyDocumentById(doc.id, doc.file);
        }
      }
    },
    [documents, onChange, onValidationError, classifyDocumentById]
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
    if (activeDocId === id) {
      setActiveDocId(null);
    }
    onChange(documents.filter((doc) => doc.id !== id));
  };

  const updateDocumentType = (id, documentType) => {
    onChange(
      documents.map((doc) =>
        doc.id === id
          ? {
              ...doc,
              documentType,
              typeConfirmed: false,
              autoClassified: false,
            }
          : doc
      )
    );
  };

  const confirmDocumentType = (id) => {
    onChange(
      documents.map((doc) =>
        doc.id === id
          ? { ...doc, typeConfirmed: true, autoClassified: false }
          : doc
      )
    );
  };

  const openDocumentDetail = (docId) => {
    scrollRestoreRef.current = window.scrollY;
    setActiveDocId(docId);
  };

  const closeDocumentDetail = () => {
    setActiveDocId(null);
    const scrollY = scrollRestoreRef.current;
    requestAnimationFrame(() => {
      window.scrollTo({ top: scrollY, left: 0, behavior: "instant" });
    });
  };

  const itemClassName = (doc) => {
    if (doc.autoClassified && doc.typeConfirmed) {
      return "document-bundle-item-auto";
    }
    if (doc.typeConfirmed) {
      return "document-bundle-item-confirmed";
    }
    if (doc.classifying) {
      return "document-bundle-item-classifying";
    }
    return "document-bundle-item-unconfirmed";
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

      {showTypeConfirmBanner && isClassifying && (
        <p className="document-type-classifying-banner" role="status">
          Classifying uploaded documents… you can choose or confirm the type for
          any file while this runs.
        </p>
      )}

      {showTypeConfirmBanner && !isClassifying && hasUnconfirmed && (
        <p className="document-type-confirm-banner" role="status">
          {needsConfirmation.length === 1
            ? "1 document needs your confirmation before analyzing."
            : `${needsConfirmation.length} documents need your confirmation before analyzing.`}
        </p>
      )}

      {documents.length > 0 && (
        <ul className="document-bundle-list">
          {documents.map((doc) => (
            <li
              key={doc.id}
              className={`document-bundle-item ${itemClassName(doc)}`}
            >
              <div className="document-bundle-item-body">
                <DocumentFilePreview
                  file={doc.file}
                  clickable
                  onClick={() => openDocumentDetail(doc.id)}
                  ariaLabel={`Open preview of ${doc.file?.name}`}
                />
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
                    <DocumentTypeControls
                      doc={doc}
                      disabled={disabled}
                      onUpdateType={updateDocumentType}
                      onConfirm={confirmDocumentType}
                    />
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {activeDocument && (
        <DocumentTypeDetailView
          document={activeDocument}
          onClose={closeDocumentDetail}
          onUpdateType={updateDocumentType}
          onConfirm={confirmDocumentType}
          disabled={disabled}
        />
      )}
    </div>
  );
}
