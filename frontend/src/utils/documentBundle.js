import {
  buildDatePromptItem,
  detectDocumentDate,
  normalizeToIsoDate,
} from "./documentDates";
import { getApiBase } from "../services/apiBase";
import { fetchBackend, parseJsonResponse } from "../services/httpUtils";
import {
  mergeClinicalContext,
  emptyClinicalContext,
  normalizePrescriptionPayload,
  uploadClinicalDocument,
  uploadPreauthDocument,
  uploadPrescription,
} from "../services/prescriptions";

export const DOCUMENT_TYPES = [
  { id: "bill", label: "Hospital bill" },
  { id: "prescription", label: "Prescription" },
  { id: "lab_report", label: "Lab report" },
  { id: "discharge_summary", label: "Discharge summary" },
  { id: "preauth_letter", label: "Pre-authorization letter" },
];

export function createBundleSession() {
  const sessionId =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return { sessionId, documents: [] };
}

export function createBundleDocument(file, documentType = null) {
  const suggestedType = documentType || guessDocumentType(file?.name || "");
  return {
    id:
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `doc-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    file,
    suggestedType,
    documentType: suggestedType,
    typeConfirmed: false,
  };
}

export function allBundleDocumentsConfirmed(documents) {
  return (
    Array.isArray(documents) &&
    documents.length > 0 &&
    documents.every((doc) => doc.typeConfirmed === true)
  );
}

export function documentTypeLabel(typeId) {
  return DOCUMENT_TYPES.find((type) => type.id === typeId)?.label || typeId;
}

export function guessDocumentType(filename) {
  const lower = String(filename || "").toLowerCase();
  if (/(^|[^a-z])rx([^a-z]|$)|prescription|presc/.test(lower)) {
    return "prescription";
  }
  if (/lab|pathology|diagnostic|blood|cbc|report/.test(lower)) {
    return "lab_report";
  }
  if (/discharge|summary|ipd/.test(lower)) {
    return "discharge_summary";
  }
  if (/pre.?auth|authorization|approval|claim|insurance|tpa|cashless/.test(lower)) {
    return "preauth_letter";
  }
  if (/bill|invoice|receipt|estimate/.test(lower)) {
    return "bill";
  }
  return "bill";
}

function dedupeByName(items, nameKey = "name") {
  const seen = new Set();
  const result = [];
  for (const item of items) {
    const name = String(item?.[nameKey] || "").trim();
    if (!name) {
      continue;
    }
    const key = name.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push({ ...item, [nameKey]: name });
  }
  return result;
}

async function uploadBill(file, location) {
  const formData = new FormData();
  formData.append("file", file);
  const params = new URLSearchParams({
    state_ut_name: location.state,
    city: location.city,
    hospital_type: location.hospitalType || "general",
  });
  const response = await fetchBackend(
    `${getApiBase()}/upload-bill?${params}`,
    { method: "POST", body: formData }
  );
  return parseJsonResponse(response);
}

function mergeBillResponses(responses) {
  const lineItems = [];
  const ocrTexts = [];
  let firstBill = null;
  let billDate = "";

  for (const response of responses) {
    if (!response) {
      continue;
    }
    if (!firstBill) {
      firstBill = response;
    }
    if (!billDate) {
      billDate = normalizeToIsoDate(response.bill_date);
    }
    lineItems.push(...(response.line_items || []));
    if (response.ocr_text) {
      ocrTexts.push(response.ocr_text);
    }
  }

  return {
    lineItems,
    scanMeta: firstBill
      ? {
          filename: firstBill.filename,
          file_type: firstBill.file_type,
          hospital: firstBill.hospital,
          comparison_settings: firstBill.comparison_settings,
          bill_date: billDate || null,
          ocr_text: ocrTexts.join("\n"),
        }
      : null,
  };
}

function mergePrescriptionResponses(responses) {
  let medicines = [];
  let tests = [];
  let procedures = [];
  let clinicalContext = emptyClinicalContext();
  let diagnosis = "";
  let diagnosisConfidence = "missing";
  let prescriber = "";
  let prescriptionDate = "";
  const ocrTexts = [];
  let firstMeta = null;

  for (const payload of responses) {
    if (!payload) {
      continue;
    }
    const normalized = normalizePrescriptionPayload(payload);
    medicines = [...medicines, ...normalized.medicines];
    tests = [...tests, ...normalized.tests];
    procedures = [...procedures, ...normalized.procedures];
    clinicalContext = mergeClinicalContext(clinicalContext, normalized.clinicalContext);
    if (!diagnosis && normalized.diagnosis) {
      diagnosis = normalized.diagnosis;
      diagnosisConfidence = payload.diagnosis_confidence || "missing";
    }
    if (!prescriber && normalized.prescriber) {
      prescriber = normalized.prescriber;
    }
    if (!prescriptionDate && normalized.prescriptionDate) {
      prescriptionDate = normalized.prescriptionDate;
    }
    if (payload.ocr_text) {
      ocrTexts.push(payload.ocr_text);
    }
    if (!firstMeta) {
      firstMeta = {
        filename: payload.filename,
        file_type: payload.file_type,
      };
    }
  }

  return {
    medicines: dedupeByName(medicines),
    tests: dedupeByName(tests),
    procedures: dedupeByName(procedures),
    clinicalContext,
    diagnosis,
    diagnosisConfidence,
    prescriptionMeta: firstMeta
      ? {
          ...firstMeta,
          prescriber,
          prescriptionDate,
          diagnosisConfidence,
          ocr_text: ocrTexts.join("\n"),
        }
      : null,
  };
}

function mergeClinicalResponses(responses) {
  let clinicalContext = emptyClinicalContext();
  for (const payload of responses) {
    clinicalContext = mergeClinicalContext(
      clinicalContext,
      payload?.clinical_context || emptyClinicalContext()
    );
  }
  return clinicalContext;
}

export function bundleHasBills(documents) {
  return documents.some((doc) => doc.documentType === "bill");
}

export function applyDocumentDatesToBundle(documents, confirmedDates) {
  const dateMap = new Map(
    (confirmedDates || []).map((item) => [item.id, normalizeToIsoDate(item.documentDate)])
  );
  return documents.map((doc) => ({
    ...doc,
    documentDate: dateMap.get(doc.id) || normalizeToIsoDate(doc.documentDate) || "",
  }));
}

export function mergeConfirmedDatesIntoBundle(merged, documents, confirmedDates) {
  const datedDocuments = applyDocumentDatesToBundle(documents, confirmedDates);
  const dateMap = new Map(
    confirmedDates.map((item) => [item.id, normalizeToIsoDate(item.documentDate)])
  );

  const sourceDocuments = datedDocuments.map((doc) => ({
    type: doc.documentType,
    filename: doc.file?.name || "document",
    file_type: doc.file?.type || null,
    document_date: dateMap.get(doc.id) || null,
  }));

  const billDate =
    confirmedDates.find((item) => item.documentType === "bill")?.documentDate ||
    merged.scanMeta?.bill_date ||
    null;

  const prescriptionDate =
    confirmedDates.find((item) => item.documentType === "prescription")
      ?.documentDate ||
    merged.prescriptionMeta?.prescriptionDate ||
    null;

  return {
    ...merged,
    sourceDocuments,
    scanMeta: merged.scanMeta
      ? {
          ...merged.scanMeta,
          bill_date: normalizeToIsoDate(billDate) || merged.scanMeta.bill_date || null,
        }
      : merged.scanMeta,
    prescriptionMeta: merged.prescriptionMeta
      ? {
          ...merged.prescriptionMeta,
          prescriptionDate:
            normalizeToIsoDate(prescriptionDate) ||
            merged.prescriptionMeta.prescriptionDate ||
            "",
        }
      : merged.prescriptionMeta,
    datedDocuments,
  };
}

export async function processDocumentBundle(documents, location) {
  const bills = documents.filter((doc) => doc.documentType === "bill");
  const prescriptions = documents.filter(
    (doc) => doc.documentType === "prescription"
  );
  const labReports = documents.filter((doc) => doc.documentType === "lab_report");
  const dischargeSummaries = documents.filter(
    (doc) => doc.documentType === "discharge_summary"
  );
  const preauthLetters = documents.filter(
    (doc) => doc.documentType === "preauth_letter"
  );

  if (bills.length && (!location?.state || !location?.city)) {
    throw new Error(
      "Please select the state/UT and city where the hospital is located."
    );
  }

  const [
    billResults,
    prescriptionResults,
    labResults,
    dischargeResults,
    preauthResults,
  ] =
    await Promise.all([
      Promise.all(bills.map((doc) => uploadBill(doc.file, location))),
      Promise.all(prescriptions.map((doc) => uploadPrescription(doc.file))),
      Promise.all(
        labReports.map((doc) => uploadClinicalDocument(doc.file, "lab_report"))
      ),
      Promise.all(
        dischargeSummaries.map((doc) =>
          uploadClinicalDocument(doc.file, "discharge_summary")
        )
      ),
      Promise.all(preauthLetters.map((doc) => uploadPreauthDocument(doc.file))),
    ]);

  const { lineItems, scanMeta } = mergeBillResponses(billResults);
  const prescriptionMerged = mergePrescriptionResponses(prescriptionResults);
  const clinicalFromDocs = mergeClinicalResponses([
    ...labResults,
    ...dischargeResults,
  ]);
  const clinicalContext = mergeClinicalContext(
    prescriptionMerged.clinicalContext,
    clinicalFromDocs
  );

  const sourceDocuments = documents.map((doc) => ({
    type: doc.documentType,
    filename: doc.file?.name || "document",
    file_type: doc.file?.type || null,
    document_date: normalizeToIsoDate(doc.documentDate) || null,
  }));

  const perDocumentDates = [
    ...bills.map((doc, index) =>
      buildDatePromptItem({
        id: doc.id,
        filename: doc.file?.name,
        documentType: "bill",
        detectedDate: detectDocumentDate("bill", billResults[index]),
      })
    ),
    ...prescriptions.map((doc, index) =>
      buildDatePromptItem({
        id: doc.id,
        filename: doc.file?.name,
        documentType: "prescription",
        detectedDate: detectDocumentDate("prescription", prescriptionResults[index]),
      })
    ),
    ...labReports.map((doc, index) =>
      buildDatePromptItem({
        id: doc.id,
        filename: doc.file?.name,
        documentType: "lab_report",
        detectedDate: detectDocumentDate("lab_report", labResults[index]),
      })
    ),
    ...dischargeSummaries.map((doc, index) =>
      buildDatePromptItem({
        id: doc.id,
        filename: doc.file?.name,
        documentType: "discharge_summary",
        detectedDate: detectDocumentDate(
          "discharge_summary",
          dischargeResults[index]
        ),
      })
    ),
    ...preauthLetters.map((doc, index) =>
      buildDatePromptItem({
        id: doc.id,
        filename: doc.file?.name,
        documentType: "preauth_letter",
        detectedDate: detectDocumentDate("preauth_letter", preauthResults[index]),
      })
    ),
  ];

  return {
    lineItems,
    scanMeta,
    prescriptionMeta: prescriptionMerged.prescriptionMeta,
    medicines: prescriptionMerged.medicines,
    tests: prescriptionMerged.tests,
    procedures: prescriptionMerged.procedures,
    diagnosis: prescriptionMerged.diagnosis,
    diagnosisConfidence: prescriptionMerged.diagnosisConfidence,
    clinicalContext,
    sourceDocuments,
    perDocumentDates,
    preauthDocuments: preauthResults,
    hasBills: bills.length > 0,
    hasPrescriptions: prescriptions.length > 0,
    hasClinicalDocs: labReports.length + dischargeSummaries.length > 0,
    hasPreauth: preauthLetters.length > 0,
  };
}
