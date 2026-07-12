import { useEffect, useRef, useState } from "react";
import {
  DOCUMENT_TYPES,
  documentShowsTypeSuggestion,
  documentTypeLabel,
  guessDocumentType,
} from "../utils/documentBundle";
import DocumentFilePreview from "./DocumentFilePreview";
import DocumentTypeDetailView from "./DocumentTypeDetailView";
import { DEFAULT_FILE_ACCEPT, validateUploadFile } from "../utils/fileUpload";
import { normalizeToIsoDate } from "../utils/documentDates";
import {
  deleteHistoricalDocument,
  extractHistoricalDocument,
  saveHistoricalDocument,
} from "../services/patientHistoricalDocuments";
import { getPatientHospitals } from "../services/patientHospitals";
import { formatHospitalLabel } from "./HospitalList";
import { classifyDocument } from "../services/prescriptions";
import DocumentExtractedDataEditor from "./DocumentExtractedDataEditor";
import {
  buildEditableExtraction,
  detectDateFromEditable,
  editableToExtractedSummary,
} from "../utils/documentExtraction";

export default function PatientHistoricalDocuments({
  userId,
  patientId,
  documents = [],
  onChange,
  disabled = false,
  embedded = false,
}) {
  const scrollRestoreRef = useRef(0);
  const manualTypeOverrideRef = useRef(false);
  const [file, setFile] = useState(null);
  const [documentType, setDocumentType] = useState("");
  const [suggestedType, setSuggestedType] = useState(null);
  const [typeConfirmed, setTypeConfirmed] = useState(false);
  const [autoClassified, setAutoClassified] = useState(false);
  const [classifying, setClassifying] = useState(false);
  const [classificationConfidence, setClassificationConfidence] = useState(null);
  const [showDetail, setShowDetail] = useState(false);
  const [documentDate, setDocumentDate] = useState("");
  const [detectedDate, setDetectedDate] = useState("");
  const [, setExtraction] = useState(null);
  const [editableExtraction, setEditableExtraction] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState(null);
  const [hospitals, setHospitals] = useState([]);
  const [hospitalsLoading, setHospitalsLoading] = useState(true);
  const [hospitalId, setHospitalId] = useState("");

  const selectedHospital = hospitals.find((entry) => entry.id === hospitalId) || null;

  useEffect(() => {
    let cancelled = false;
    const loadHospitals = async () => {
      if (!userId || !patientId) {
        setHospitals([]);
        setHospitalsLoading(false);
        return;
      }
      setHospitalsLoading(true);
      try {
        const list = await getPatientHospitals(userId, patientId);
        if (!cancelled) {
          setHospitals(list);
          setHospitalId((current) =>
            current && list.some((entry) => entry.id === current)
              ? current
              : list[0]?.id || ""
          );
        }
      } catch {
        if (!cancelled) {
          setHospitals([]);
        }
      } finally {
        if (!cancelled) {
          setHospitalsLoading(false);
        }
      }
    };
    loadHospitals();
    return () => {
      cancelled = true;
    };
  }, [userId, patientId]);

  const resetUploadState = () => {
    setFile(null);
    setDocumentDate("");
    setDetectedDate("");
    setExtraction(null);
    setEditableExtraction(null);
    setTypeConfirmed(false);
    setAutoClassified(false);
    setClassifying(false);
    setClassificationConfidence(null);
    setShowDetail(false);
    manualTypeOverrideRef.current = false;
  };

  const applyClassification = (result) => {
    if (manualTypeOverrideRef.current) {
      return;
    }
    const classifiedType = result?.document_type || null;
    const nextType = classifiedType || suggestedType || documentType || "";
    const confidence = result?.confidence === "high" ? "high" : "low";
    const isAuto = Boolean(classifiedType) && confidence === "high";
    setSuggestedType(classifiedType || suggestedType);
    setDocumentType(nextType);
    setClassificationConfidence(confidence);
    setAutoClassified(isAuto);
    setTypeConfirmed(isAuto);
  };

  const classifySelectedFile = async (nextFile) => {
    setClassifying(true);
    manualTypeOverrideRef.current = false;
    setTypeConfirmed(false);
    setAutoClassified(false);
    setClassificationConfidence(null);
    setExtraction(null);
    setEditableExtraction(null);
    setDetectedDate("");
    setDocumentDate("");
    try {
      const result = await classifyDocument(nextFile);
      applyClassification(result);
    } catch {
      setClassificationConfidence("low");
      if (!manualTypeOverrideRef.current) {
        setTypeConfirmed(false);
        setAutoClassified(false);
      }
    } finally {
      setClassifying(false);
    }
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
    setSuggestedType(guessed || null);
    setDocumentType(guessed || "");
    setTypeConfirmed(false);
    setAutoClassified(false);
    setClassifying(true);
    setClassificationConfidence(null);
    setDocumentDate("");
    setDetectedDate("");
    setExtraction(null);
    setEditableExtraction(null);
    setError("");
    classifySelectedFile(nextFile);
  };

  const openDetail = () => {
    scrollRestoreRef.current = window.scrollY;
    setShowDetail(true);
  };

  const closeDetail = () => {
    setShowDetail(false);
    const scrollY = scrollRestoreRef.current;
    requestAnimationFrame(() => {
      window.scrollTo({ top: scrollY, left: 0, behavior: "instant" });
    });
  };

  const handleExtract = async () => {
    if (!file) {
      setError("Choose a document to upload.");
      return;
    }
    if (!selectedHospital) {
      setError("Add and select a hospital before uploading documents.");
      return;
    }
    if (!typeConfirmed) {
      setError("Confirm the document type before extracting.");
      return;
    }

    setExtracting(true);
    setError("");
    try {
      const result = await extractHistoricalDocument(
        file,
        documentType,
        selectedHospital
      );
      const editable = buildEditableExtraction(documentType, result);
      const foundDate = detectDateFromEditable(documentType, editable);
      setExtraction(result);
      setEditableExtraction(editable);
      setDetectedDate(foundDate);
      setDocumentDate(foundDate);
    } catch (err) {
      setExtraction(null);
      setEditableExtraction(null);
      setDetectedDate("");
      setDocumentDate("");
      setError(err.message || "Unable to extract document.");
    } finally {
      setExtracting(false);
    }
  };

  const handleSave = async () => {
    if (!editableExtraction) {
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

    if (!selectedHospital) {
      setError("Select a hospital before saving.");
      return;
    }

    setUploading(true);
    setError("");
    try {
      const extractedSummary = editableToExtractedSummary(
        documentType,
        editableExtraction
      );
      const saved = await saveHistoricalDocument(userId, patientId, {
        file,
        filename: file.name,
        documentType,
        documentDate: normalizeToIsoDate(documentDate),
        extractedSummary,
        hospitalId: selectedHospital.id,
        hospitalName: selectedHospital.name,
        hospitalCity: selectedHospital.city,
        hospitalState: selectedHospital.state,
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

  const updateDocumentType = (_id, nextType) => {
    manualTypeOverrideRef.current = true;
    setDocumentType(nextType);
    setTypeConfirmed(false);
    setAutoClassified(false);
    setExtraction(null);
    setEditableExtraction(null);
    setDetectedDate("");
    setDocumentDate("");
  };

  const confirmDocumentType = () => {
    manualTypeOverrideRef.current = true;
    setTypeConfirmed(true);
    setAutoClassified(false);
  };

  const detailDocument = file
    ? {
        id: "historical-upload",
        file,
        documentType,
        suggestedType,
        typeConfirmed,
        autoClassified,
        classifying,
        classificationConfidence,
      }
    : null;

  const HeadingTag = embedded ? "h3" : "h2";
  const extractionBusy = extracting || uploading;
  const isAutoClassified = autoClassified && typeConfirmed;

  return (
    <section
      className={`patient-historical-docs${
        embedded ? " patient-historical-docs-embedded" : ""
      }`}
    >
      <HeadingTag>Historical documents</HeadingTag>
      <p className="clinical-history-hint">
        Upload older reports with the date they relate to. Select the hospital
        where the document was issued. We read dates from documents when possible;
        otherwise you will be asked to enter them.
      </p>

      {hospitalsLoading && <p className="auth-info">Loading hospitals...</p>}

      {!hospitalsLoading && !hospitals.length && (
        <p className="clinical-history-hint">
          Add a hospital in the Hospitals section above before uploading documents.
        </p>
      )}

      {hospitals.length > 0 && (
        <label className="setting-field setting-field-full">
          <span>Hospital</span>
          <select
            value={hospitalId}
            onChange={(event) => setHospitalId(event.target.value)}
            disabled={disabled || extractionBusy}
          >
            {hospitals.map((hospital) => (
              <option key={hospital.id} value={hospital.id}>
                {formatHospitalLabel(hospital)}
              </option>
            ))}
          </select>
        </label>
      )}

      <div className="patient-historical-upload">
        <label className="setting-field setting-field-full">
          <span>Document file</span>
          <input
            type="file"
            accept={DEFAULT_FILE_ACCEPT}
            onChange={handleFileChange}
            disabled={disabled || extractionBusy || !selectedHospital}
          />
        </label>

        {file && (
          <div
            className={`document-upload-preview-panel ${
              isAutoClassified
                ? "document-bundle-item-auto"
                : typeConfirmed
                  ? "document-bundle-item-confirmed"
                  : "document-bundle-item-unconfirmed"
            }`}
          >
            <DocumentFilePreview
              file={file}
              clickable
              onClick={openDetail}
              ariaLabel={`Open preview of ${file.name}`}
            />
            <div className="document-upload-preview-details">
              {classifying && (
                <p className="document-classifying-status" role="status">
                  Classifying document… you can choose or confirm the type below
                  while this runs.
                </p>
              )}
              {!classifying && isAutoClassified ? (
                <p className="document-auto-classified-note">
                  Classified by the system as{" "}
                  <strong>{documentTypeLabel(documentType)}</strong>
                </p>
              ) : !classifying ? (
                <p className="document-suggested-type">
                  {typeConfirmed
                    ? `Type: ${documentTypeLabel(documentType)}`
                    : documentShowsTypeSuggestion({
                        suggestedType,
                        documentType,
                        typeConfirmed,
                      })
                      ? `Please confirm: suggested ${documentTypeLabel(suggestedType)}`
                      : "Please select a document type."}
                </p>
              ) : null}
              <label className="setting-field setting-field-full">
                <span>Document type</span>
                <select
                  className={`document-type-select ${
                    isAutoClassified ? "document-type-select-auto" : ""
                  }`}
                  value={documentType}
                  onChange={(event) => updateDocumentType(null, event.target.value)}
                  disabled={disabled}
                >
                  <option value="" disabled>
                    Select document type
                  </option>
                  {DOCUMENT_TYPES.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </label>
              {typeConfirmed ? (
                <span
                  className={`document-type-confirmed-badge ${
                    isAutoClassified ? "document-type-auto-badge" : ""
                  }`}
                >
                  {isAutoClassified ? "✓ Classified by system" : "✓ Type confirmed"}
                </span>
              ) : (
                <button
                  type="button"
                  className="bill-editor-secondary document-type-confirm-btn"
                  onClick={confirmDocumentType}
                  disabled={disabled || !documentType}
                >
                  Confirm type
                </button>
              )}
            </div>
          </div>
        )}

        {file && typeConfirmed && !editableExtraction && (
          <button
            type="button"
            className="analyze-btn"
            onClick={handleExtract}
            disabled={disabled || extractionBusy}
          >
            {extracting ? "Extracting..." : "Extract document"}
          </button>
        )}

        {editableExtraction && (
          <>
            <DocumentExtractedDataEditor
              editable={editableExtraction}
              onChange={(nextEditable) => {
                setEditableExtraction(nextEditable);
                const nextDate = detectDateFromEditable(documentType, nextEditable);
                if (nextDate) {
                  setDocumentDate(nextDate);
                  setDetectedDate(nextDate);
                }
              }}
              disabled={disabled || extractionBusy}
            />
            <label className="setting-field setting-field-full">
              <span>Document date</span>
              <input
                type="date"
                value={normalizeToIsoDate(documentDate)}
                onChange={(event) => setDocumentDate(event.target.value)}
                disabled={disabled || extractionBusy}
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
              disabled={disabled || extractionBusy || !normalizeToIsoDate(documentDate)}
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
                {doc.hospitalName ? ` · ${doc.hospitalName}` : ""}
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

      {showDetail && detailDocument && (
        <DocumentTypeDetailView
          document={detailDocument}
          onClose={closeDetail}
          onUpdateType={updateDocumentType}
          onConfirm={confirmDocumentType}
          disabled={disabled}
        />
      )}
    </section>
  );
}
