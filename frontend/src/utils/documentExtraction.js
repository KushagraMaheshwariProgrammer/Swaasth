import {
  buildDatePromptItem,
  detectDocumentDate,
  normalizeToIsoDate,
} from "./documentDates";
import {
  emptyClinicalContext,
  mergeClinicalContext,
  normalizePrescriptionPayload,
} from "../services/prescriptions";

const CATEGORY_OPTIONS = ["medicine", "test", "procedure", "other"];

const emptyLineItem = () => ({
  item_name: "",
  quantity: 1,
  unit_price: 0,
  total_price: 0,
  category: "other",
});

const emptyNamedItem = () => ({ name: "" });

const emptySymptom = () => ({ name: "", duration: "", severity: "" });

const emptyTestResult = () => ({
  test_name: "",
  value: "",
  unit: "",
  result: "",
  reference_range: "",
});

const emptyPreauthItem = () => ({
  name: "",
  approved_amount: "",
  notes: "",
});

function normalizeLineItem(item) {
  const category = CATEGORY_OPTIONS.includes(item?.category) ? item.category : "other";
  const quantity = Math.max(Number(item?.quantity) || 0, 0);
  const unitPrice = Math.max(Number(item?.unit_price) || 0, 0);
  let totalPrice = Math.max(Number(item?.total_price) || 0, 0);
  if (totalPrice <= 0 && quantity > 0 && unitPrice > 0) {
    totalPrice = Math.round(quantity * unitPrice * 100) / 100;
  }
  return {
    item_name: String(item?.item_name ?? item?.name ?? "").trim(),
    quantity,
    unit_price: unitPrice,
    total_price: totalPrice,
    category,
  };
}

function normalizeSymptom(item) {
  return {
    name: String(item?.name || "").trim(),
    duration: String(item?.duration || "").trim(),
    severity: String(item?.severity || "").trim(),
  };
}

function normalizeTestResult(item) {
  return {
    test_name: String(item?.test_name || "").trim(),
    value: String(item?.value ?? "").trim(),
    unit: String(item?.unit || "").trim(),
    result: String(item?.result || "").trim(),
    reference_range: String(item?.reference_range || "").trim(),
  };
}

/** Convert an API extraction payload into a per-document editable structure. */
export function buildEditableExtraction(documentType, payload) {
  if (!payload) {
    return { documentType };
  }

  if (documentType === "bill") {
    const items = (payload.line_items || []).map(normalizeLineItem);
    return {
      documentType,
      line_items: items.length ? items : [emptyLineItem()],
      hospital_name: payload.hospital?.name_from_bill || "",
      bill_date: normalizeToIsoDate(payload.bill_date),
      ocr_text: payload.ocr_text || "",
    };
  }

  if (documentType === "prescription") {
    const normalized = normalizePrescriptionPayload(payload);
    return {
      documentType,
      diagnosis: normalized.diagnosis || "",
      medicines: normalized.medicines.length
        ? normalized.medicines
        : [emptyNamedItem()],
      tests: normalized.tests.length ? normalized.tests : [emptyNamedItem()],
      procedures: normalized.procedures.length
        ? normalized.procedures
        : [emptyNamedItem()],
      prescription_date: normalizeToIsoDate(normalized.prescriptionDate),
      prescriber: normalized.prescriber || "",
      symptoms: normalized.clinicalContext?.symptoms?.length
        ? normalized.clinicalContext.symptoms.map(normalizeSymptom)
        : [emptySymptom()],
      test_results: normalized.clinicalContext?.test_results?.length
        ? normalized.clinicalContext.test_results.map(normalizeTestResult)
        : [emptyTestResult()],
      ocr_text: payload.ocr_text || "",
    };
  }

  if (documentType === "lab_report") {
    const ctx = payload.clinical_context || {};
    return {
      documentType,
      lab_name: payload.lab_name || "",
      report_date: normalizeToIsoDate(payload.report_date),
      symptoms: (ctx.symptoms || []).length
        ? ctx.symptoms.map(normalizeSymptom)
        : [emptySymptom()],
      test_results: (ctx.test_results || []).length
        ? ctx.test_results.map(normalizeTestResult)
        : [emptyTestResult()],
      ocr_text: payload.ocr_text || "",
    };
  }

  if (documentType === "discharge_summary") {
    const ctx = payload.clinical_context || {};
    return {
      documentType,
      diagnosis: payload.diagnosis || "",
      discharge_date: normalizeToIsoDate(payload.discharge_date),
      symptoms: (ctx.symptoms || []).length
        ? ctx.symptoms.map(normalizeSymptom)
        : [emptySymptom()],
      test_results: (ctx.test_results || []).length
        ? ctx.test_results.map(normalizeTestResult)
        : [emptyTestResult()],
      procedures: (payload.procedures || []).length
        ? payload.procedures.map((item) => ({ name: String(item?.name || "").trim() }))
        : [emptyNamedItem()],
      ocr_text: payload.ocr_text || "",
    };
  }

  if (documentType === "preauth_letter") {
    const items = (payload.approved_items || []).map((item) => ({
      name: String(item?.name || "").trim(),
      approved_amount:
        item?.approved_amount != null ? String(item.approved_amount) : "",
      notes: String(item?.notes || "").trim(),
    }));
    return {
      documentType,
      authorization_id: payload.authorization_id || "",
      authorization_date: normalizeToIsoDate(payload.authorization_date),
      insurer_or_scheme: payload.insurer_or_scheme || "",
      approved_items: items.length ? items : [emptyPreauthItem()],
      ocr_text: payload.ocr_text || "",
    };
  }

  return { documentType, ocr_text: payload.ocr_text || "" };
}

function filterNamedItems(items) {
  return (items || [])
    .map((item) => ({ ...item, name: String(item?.name || "").trim() }))
    .filter((item) => item.name);
}

function filterLineItems(items) {
  return (items || []).map(normalizeLineItem).filter((item) => item.item_name);
}

function filterSymptoms(items) {
  return (items || []).map(normalizeSymptom).filter((item) => item.name);
}

function filterTestResults(items) {
  return (items || []).map(normalizeTestResult).filter((item) => item.test_name);
}

function clinicalContextFromEditable(editable, sources = {}) {
  return mergeClinicalContext(emptyClinicalContext(), {
    symptoms: filterSymptoms(editable.symptoms),
    test_results: filterTestResults(editable.test_results),
    symptoms_source: sources.symptoms_source || "manual",
    test_results_source: sources.test_results_source || "manual",
  });
}

/** Merge per-document edited extractions into the bundle shape used by App.jsx. */
export function mergeEditedExtractionsToBundle(documents, location) {
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

  const lineItems = [];
  const ocrTexts = [];
  let firstBillMeta = null;
  let billDate = "";

  for (const doc of bills) {
    const editable = doc.editableExtraction || {};
    const items = filterLineItems(editable.line_items);
    lineItems.push(...items);
    if (editable.ocr_text) {
      ocrTexts.push(editable.ocr_text);
    }
    if (!firstBillMeta) {
      firstBillMeta = {
        filename: doc.file?.name || "bill",
        file_type: doc.file?.type || null,
        hospital: { name_from_bill: editable.hospital_name || null },
        comparison_settings: location
          ? {
              state_ut_name: location.state,
              city: location.city,
              hospital_type: location.hospitalType || "general",
            }
          : {},
        bill_date: editable.bill_date || null,
      };
      billDate = editable.bill_date || "";
    }
  }

  let medicines = [];
  let tests = [];
  let procedures = [];
  let clinicalContext = emptyClinicalContext();
  let diagnosis = "";
  let diagnosisConfidence = "missing";
  let prescriber = "";
  let prescriptionDate = "";
  let prescriptionMeta = null;

  for (const doc of prescriptions) {
    const editable = doc.editableExtraction || {};
    medicines = [...medicines, ...filterNamedItems(editable.medicines)];
    tests = [...tests, ...filterNamedItems(editable.tests)];
    procedures = [...procedures, ...filterNamedItems(editable.procedures)];
    clinicalContext = mergeClinicalContext(
      clinicalContext,
      clinicalContextFromEditable(editable, {
        symptoms_source: "prescription",
        test_results_source: "prescription",
      })
    );
    if (!diagnosis && editable.diagnosis?.trim()) {
      diagnosis = editable.diagnosis.trim();
    }
    if (!prescriber && editable.prescriber?.trim()) {
      prescriber = editable.prescriber.trim();
    }
    if (!prescriptionDate && editable.prescription_date) {
      prescriptionDate = editable.prescription_date;
    }
    if (editable.ocr_text) {
      ocrTexts.push(editable.ocr_text);
    }
    if (!prescriptionMeta) {
      prescriptionMeta = {
        filename: doc.file?.name || "prescription",
        file_type: doc.file?.type || null,
        prescriber,
        prescriptionDate,
        diagnosisConfidence,
        ocr_text: editable.ocr_text || "",
      };
    }
  }

  for (const doc of labReports) {
    const editable = doc.editableExtraction || {};
    clinicalContext = mergeClinicalContext(
      clinicalContext,
      clinicalContextFromEditable(editable, {
        symptoms_source: "lab_report",
        test_results_source: "lab_report",
      })
    );
    if (editable.ocr_text) {
      ocrTexts.push(editable.ocr_text);
    }
  }

  for (const doc of dischargeSummaries) {
    const editable = doc.editableExtraction || {};
    clinicalContext = mergeClinicalContext(
      clinicalContext,
      clinicalContextFromEditable(editable, {
        symptoms_source: "discharge",
        test_results_source: "discharge",
      })
    );
    procedures = [
      ...procedures,
      ...filterNamedItems(editable.procedures),
    ];
    if (!diagnosis && editable.diagnosis?.trim()) {
      diagnosis = editable.diagnosis.trim();
    }
    if (editable.ocr_text) {
      ocrTexts.push(editable.ocr_text);
    }
  }

  const preauthDocuments = preauthLetters.map((doc) => {
    const editable = doc.editableExtraction || {};
    return {
      filename: doc.file?.name || "preauth",
      file_type: doc.file?.type || null,
      document_type: "preauth_letter",
      authorization_id: editable.authorization_id || null,
      authorization_date: editable.authorization_date || null,
      insurer_or_scheme: editable.insurer_or_scheme || null,
      approved_items: (editable.approved_items || [])
        .map((item) => ({
          name: String(item?.name || "").trim(),
          approved_amount:
            item?.approved_amount === "" || item?.approved_amount == null
              ? null
              : Number(item.approved_amount),
          notes: String(item?.notes || "").trim() || null,
        }))
        .filter((item) => item.name),
      ocr_text: editable.ocr_text || "",
    };
  });

  const perDocumentDates = documents.map((doc) => {
    const editable = doc.editableExtraction || {};
    let detectedDate = doc.documentDate || "";
    if (doc.documentType === "bill") {
      detectedDate = editable.bill_date || detectedDate;
    } else if (doc.documentType === "prescription") {
      detectedDate = editable.prescription_date || detectedDate;
    } else if (doc.documentType === "lab_report") {
      detectedDate = editable.report_date || detectedDate;
    } else if (doc.documentType === "discharge_summary") {
      detectedDate = editable.discharge_date || detectedDate;
    } else if (doc.documentType === "preauth_letter") {
      detectedDate = editable.authorization_date || detectedDate;
    }
    return buildDatePromptItem({
      id: doc.id,
      filename: doc.file?.name,
      documentType: doc.documentType,
      detectedDate,
    });
  });

  const scanMeta = firstBillMeta
    ? {
        ...firstBillMeta,
        bill_date: normalizeToIsoDate(billDate) || null,
        ocr_text: ocrTexts.join("\n"),
      }
    : null;

  if (prescriptionMeta) {
    prescriptionMeta = {
      ...prescriptionMeta,
      prescriber,
      prescriptionDate: normalizeToIsoDate(prescriptionDate) || "",
      ocr_text: prescriptionMeta.ocr_text || ocrTexts.join("\n"),
    };
  }

  return {
    lineItems,
    scanMeta,
    prescriptionMeta,
    medicines: dedupeByName(medicines),
    tests: dedupeByName(tests),
    procedures: dedupeByName(procedures),
    diagnosis,
    diagnosisConfidence,
    clinicalContext,
    preauthDocuments,
    perDocumentDates,
    hasBills: bills.length > 0,
    hasPrescriptions: prescriptions.length > 0,
    hasClinicalDocs: labReports.length + dischargeSummaries.length > 0,
    hasPreauth: preauthLetters.length > 0,
    sourceDocuments: documents.map((doc) => ({
      type: doc.documentType,
      filename: doc.file?.name || "document",
      file_type: doc.file?.type || null,
      document_date:
        normalizeToIsoDate(perDocumentDates.find((item) => item.id === doc.id)?.detectedDate) ||
        null,
    })),
  };
}

function dedupeByName(items) {
  const seen = new Set();
  const result = [];
  for (const item of items) {
    const name = String(item?.name || "").trim();
    if (!name) {
      continue;
    }
    const key = name.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push({ ...item, name });
  }
  return result;
}

/** Attach editable extraction payloads to bundle documents from processDocumentBundle results. */
export function attachExtractionsToDocuments(documents, extractionByDocId) {
  return documents.map((doc) => {
    const raw = extractionByDocId[doc.id];
    if (!raw) {
      return doc;
    }
    return {
      ...doc,
      rawExtraction: raw,
      editableExtraction: buildEditableExtraction(doc.documentType, raw),
      extractionError: null,
    };
  });
}

/** Build editable extraction from raw API payload (for historical single-doc flow). */
export function editableToExtractedSummary(documentType, editable) {
  if (!editable) {
    return {};
  }

  if (documentType === "prescription") {
    const ctx = clinicalContextFromEditable(editable, {
      symptoms_source: "prescription",
      test_results_source: "prescription",
    });
    return {
      diagnosis: editable.diagnosis || "",
      symptoms: ctx.symptoms,
      test_results: ctx.test_results,
      medicines: filterNamedItems(editable.medicines),
      tests: filterNamedItems(editable.tests),
      procedures: filterNamedItems(editable.procedures),
      ocr_text: editable.ocr_text || "",
    };
  }

  if (documentType === "bill") {
    return {
      diagnosis: "",
      line_items: filterLineItems(editable.line_items),
      ocr_text: editable.ocr_text || "",
    };
  }

  const ctx = clinicalContextFromEditable(editable);
  return {
    diagnosis: editable.diagnosis || "",
    clinical_context: ctx,
    symptoms: ctx.symptoms,
    test_results: ctx.test_results,
    procedures: filterNamedItems(editable.procedures),
    ocr_text: editable.ocr_text || "",
  };
}

export function detectDateFromEditable(documentType, editable) {
  if (!editable) {
    return "";
  }
  switch (documentType) {
    case "prescription":
      return normalizeToIsoDate(editable.prescription_date);
    case "bill":
      return normalizeToIsoDate(editable.bill_date);
    case "lab_report":
      return normalizeToIsoDate(editable.report_date);
    case "discharge_summary":
      return normalizeToIsoDate(editable.discharge_date);
    case "preauth_letter":
      return normalizeToIsoDate(editable.authorization_date);
    default:
      return "";
  }
}

export { detectDocumentDate };
