import { getApiBase } from "./apiBase";
import { fetchJson, LONG_FETCH_TIMEOUT_MS } from "./httpUtils";
import { getPatientAge, getPatientBirthYear } from "../utils/patientAge";

export function emptyClinicalContext() {
  return {
    symptoms: [],
    test_results: [],
    symptoms_source: "manual",
    test_results_source: "manual",
  };
}

export function mergeClinicalContext(manual, extracted) {
  const base = emptyClinicalContext();
  const manualCtx = manual || base;
  const extractedCtx = extracted || base;

  const symptoms = [];
  const seenSymptoms = new Set();
  for (const item of [...(manualCtx.symptoms || []), ...(extractedCtx.symptoms || [])]) {
    const name = String(item?.name || "").trim();
    if (!name) {
      continue;
    }
    const key = name.toLowerCase();
    if (seenSymptoms.has(key)) {
      continue;
    }
    seenSymptoms.add(key);
    symptoms.push({
      name,
      duration: item.duration || "",
      severity: item.severity || "",
    });
  }

  const testResults = [];
  const testIndex = new Map();
  for (const item of [...(extractedCtx.test_results || []), ...(manualCtx.test_results || [])]) {
    const testName = String(item?.test_name || "").trim();
    if (!testName) {
      continue;
    }
    const key = testName.toLowerCase();
    const normalized = {
      test_name: testName,
      value: item.value || "",
      unit: item.unit || "",
      result: item.result || "",
      reference_range: item.reference_range || "",
    };
    if (testIndex.has(key)) {
      testResults[testIndex.get(key)] = normalized;
    } else {
      testIndex.set(key, testResults.length);
      testResults.push(normalized);
    }
  }

  return {
    symptoms,
    test_results: testResults,
    symptoms_source: manualCtx.symptoms?.length
      ? "manual"
      : extractedCtx.symptoms_source || "manual",
    test_results_source: manualCtx.test_results?.length
      ? "manual"
      : extractedCtx.test_results_source || "manual",
  };
}

export function clinicalContextToApiPayload(clinicalContext) {
  const ctx = clinicalContext || emptyClinicalContext();
  return {
    symptoms: (ctx.symptoms || [])
      .filter((item) => String(item?.name || "").trim())
      .map((item) => ({
        name: String(item.name).trim(),
        duration: item.duration?.trim() || null,
        severity: item.severity?.trim() || null,
      })),
    test_results: (ctx.test_results || [])
      .filter((item) => String(item?.test_name || "").trim())
      .map((item) => ({
        test_name: String(item.test_name).trim(),
        value: item.value?.trim() || null,
        unit: item.unit?.trim() || null,
        result: item.result?.trim() || null,
        reference_range: item.reference_range?.trim() || null,
      })),
  };
}

export function hasClinicalData(clinicalContext) {
  const payload = clinicalContextToApiPayload(clinicalContext);
  return payload.symptoms.length > 0 || payload.test_results.length > 0;
}

export async function classifyDocument(file) {
  const formData = new FormData();
  formData.append("file", file);
  return fetchJson(`${getApiBase()}/classify-document`, {
    method: "POST",
    body: formData,
  });
}

export async function uploadPrescription(file) {
  const formData = new FormData();
  formData.append("file", file);
  return fetchJson(`${getApiBase()}/upload-prescription`, {
    method: "POST",
    body: formData,
    timeoutMs: LONG_FETCH_TIMEOUT_MS,
  });
}

export async function uploadClinicalDocument(file, documentType) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("document_type", documentType);
  return fetchJson(`${getApiBase()}/upload-clinical-document`, {
    method: "POST",
    body: formData,
    timeoutMs: LONG_FETCH_TIMEOUT_MS,
  });
}

export async function uploadPreauthDocument(file) {
  const formData = new FormData();
  formData.append("file", file);
  return fetchJson(`${getApiBase()}/upload-preauth`, {
    method: "POST",
    body: formData,
    timeoutMs: LONG_FETCH_TIMEOUT_MS,
  });
}

export async function fetchStgConditions() {
  const payload = await fetchJson(`${getApiBase()}/api/stg/conditions`);
  return payload?.conditions || [];
}

export async function analyzeTreatment({
  diagnosis,
  diagnosisUserProvided = false,
  diagnosisConfidence = null,
  medicines = [],
  tests = [],
  procedures = [],
  billItems = [],
  symptoms = [],
  testResults = [],
  patient = null,
  ocrText = "",
  clinicalHistory = null,
}) {
  return fetchJson(`${getApiBase()}/analyze-treatment`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    timeoutMs: LONG_FETCH_TIMEOUT_MS,
    body: JSON.stringify({
      diagnosis,
      diagnosis_user_provided: diagnosisUserProvided,
      diagnosis_confidence: diagnosisConfidence,
      medicines,
      tests,
      procedures,
      bill_items: billItems,
      symptoms,
      test_results: testResults,
      patient_id: patient?.id || null,
      patient_name: patient?.name || null,
      patient_birth_year: getPatientBirthYear(patient),
      patient_age: getPatientAge(patient),
      patient_gender: patient?.gender || null,
      ocr_text: ocrText || null,
      clinical_history: clinicalHistory,
    }),
  });
}

export function normalizePrescriptionPayload(payload) {
  const clinicalContext = mergeClinicalContext(
    emptyClinicalContext(),
    payload?.clinical_context || {
      symptoms: payload?.symptoms || [],
      test_results: [],
      symptoms_source: "prescription",
    }
  );
  return {
    diagnosis: payload?.diagnosis || "",
    diagnosisConfidence: payload?.diagnosis_confidence || "missing",
    prescriber: payload?.prescriber || "",
    prescriptionDate: payload?.prescription_date || "",
    clinicalContext,
    medicines: (payload?.medicines || []).map((item) => ({
      name: String(item?.name || "").trim(),
      dose: item?.dose || "",
      frequency: item?.frequency || "",
      duration: item?.duration || "",
    })),
    tests: (payload?.tests || []).map((item) => ({
      name: String(item?.name || "").trim(),
    })),
    procedures: (payload?.procedures || []).map((item) => ({
      name: String(item?.name || "").trim(),
    })),
  };
}
