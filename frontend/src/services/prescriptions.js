import { Capacitor } from "@capacitor/core";
import { fetchJson } from "./httpUtils";

const API_BASE =
  import.meta.env.VITE_API_BASE ??
  (Capacitor.isNativePlatform() ? "http://10.0.2.2:8000" : "");

export async function uploadPrescription(file) {
  const formData = new FormData();
  formData.append("file", file);
  return fetchJson(`${API_BASE}/upload-prescription`, {
    method: "POST",
    body: formData,
  });
}

export async function fetchStgConditions() {
  const payload = await fetchJson(`${API_BASE}/api/stg/conditions`);
  return payload?.conditions || [];
}

export async function analyzeTreatment({
  diagnosis,
  diagnosisUserProvided = false,
  medicines = [],
  tests = [],
  procedures = [],
  billItems = [],
  patient = null,
}) {
  return fetchJson(`${API_BASE}/analyze-treatment`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      diagnosis,
      diagnosis_user_provided: diagnosisUserProvided,
      medicines,
      tests,
      procedures,
      bill_items: billItems,
      patient_id: patient?.id || null,
      patient_name: patient?.name || null,
    }),
  });
}

export function normalizePrescriptionPayload(payload) {
  return {
    diagnosis: payload?.diagnosis || "",
    diagnosisConfidence: payload?.diagnosis_confidence || "missing",
    prescriber: payload?.prescriber || "",
    prescriptionDate: payload?.prescription_date || "",
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
