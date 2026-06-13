import { Capacitor } from "@capacitor/core";

// Mirrors the API base resolution used in App.jsx so the Aarogya Bhadratha
// service talks to the same backend on web and Android.
export const API_BASE =
  import.meta.env.VITE_API_BASE ??
  (Capacitor.isNativePlatform() ? "http://10.0.2.2:8000" : "");

const BASE = `${API_BASE}/api/aarogya-bhadratha`;

function backendUnreachableMessage() {
  if (Capacitor.isNativePlatform()) {
    return (
      "Could not reach the Swaasth backend. On your Mac run: cd backend && ./run_dev.sh " +
      "(it must listen on 0.0.0.0:8000), then try again."
    );
  }
  return (
    "Could not reach the Swaasth backend. Start it with: cd backend && ./run_dev.sh " +
    "(port 8000), then try again."
  );
}

async function parseJson(response) {
  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }
  if (!response.ok) {
    const detail = payload?.detail;
    const message = Array.isArray(detail)
      ? detail.map((entry) => entry.msg).join(", ")
      : detail;
    if (message) {
      throw new Error(message);
    }
    if (response.status === 404) {
      throw new Error(
        "Aarogya Bhadratha endpoint not found (404). Restart the backend so the new routes load."
      );
    }
    if (response.status >= 502 && response.status <= 504) {
      throw new Error(backendUnreachableMessage());
    }
    throw new Error(`Aarogya Bhadratha request failed (HTTP ${response.status}).`);
  }
  return payload;
}

// fetch wrapper that turns network failures (backend down) into a clear message.
async function request(url, options) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    if (error?.message === "Failed to fetch" || error?.name === "TypeError") {
      throw new Error(backendUnreachableMessage());
    }
    throw error;
  }
  return parseJson(response);
}

export async function extractAarogyaBill(file) {
  const formData = new FormData();
  formData.append("file", file);
  return request(`${API_BASE}/api/aarogya-bhadratha/extract-bill`, {
    method: "POST",
    body: formData,
  });
}

export async function verifyHospital({ hospitalName, district = "", address = "" }) {
  return request(`${BASE}/verify-hospital`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      hospital_name: hospitalName || "",
      district,
      address,
    }),
  });
}

export async function compareRates(body) {
  return request(`${BASE}/compare-rates`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function searchHospitals({
  query = "",
  district = "",
  speciality = "",
  page = 1,
  limit = 20,
} = {}) {
  const params = new URLSearchParams();
  if (query) params.set("query", query);
  if (district) params.set("district", district);
  if (speciality) params.set("speciality", speciality);
  params.set("page", String(page));
  params.set("limit", String(limit));
  return request(`${BASE}/hospitals/search?${params}`);
}

export async function getDistricts() {
  return request(`${BASE}/districts`);
}

export async function getSpecialities() {
  return request(`${BASE}/specialities`);
}

export function reportPdfUrl(reportId) {
  return `${BASE}/reports/${reportId}/pdf`;
}

// Render the report PDF from the full client-held report object so it works
// for both freshly generated and reopened (history) reports.
async function fetchReportPdfBlob(report) {
  const response = await fetch(`${BASE}/reports/render-pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(report),
  });
  if (!response.ok) {
    throw new Error("Could not generate the report PDF.");
  }
  return response.blob();
}

export async function openReportPdf(report) {
  const blob = await fetchReportPdfBlob(report);
  const blobUrl = URL.createObjectURL(blob);
  window.open(blobUrl, "_blank", "noopener");
}

export async function downloadReportPdf(report, filename = "aarogya-bhadratha-report.pdf") {
  const blob = await fetchReportPdfBlob(report);
  const blobUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(blobUrl);
}

export async function shareReportPdf(report) {
  const blob = await fetchReportPdfBlob(report);
  const filename = "aarogya-bhadratha-report.pdf";
  const file =
    typeof File !== "undefined"
      ? new File([blob], filename, { type: "application/pdf" })
      : null;

  if (file && navigator.canShare?.({ files: [file] }) && navigator.share) {
    try {
      await navigator.share({
        title: "Aarogya Bhadratha Bill Comparison Report",
        text: "Aarogya Bhadratha Bill Comparison Report",
        files: [file],
      });
      return true;
    } catch (error) {
      if (error?.name === "AbortError") {
        return false;
      }
    }
  }

  // Fallback: open the PDF so the user can use the OS share/save sheet.
  const blobUrl = URL.createObjectURL(blob);
  window.open(blobUrl, "_blank", "noopener");
  return false;
}

/**
 * Shape an Aarogya Bhadratha report into a bill-history entry that is
 * compatible with the existing history list (computeBillSummary, title,
 * patient name) while preserving the full report for reopening.
 */
export function buildAarogyaBillEntry(report, patient) {
  const items = report?.comparison?.items ?? [];
  const matched = report?.hospital?.matched_hospital ?? {};
  const lineItems = items.map((item) => ({
    item_name: item.item_name,
    quantity: item.quantity,
    total_price: item.total_price,
    price_difference:
      item.status === "Above Approved Rate" ? item.excess_amount ?? 0 : 0,
    flag: item.status === "Above Approved Rate" ? "overpriced" : "acceptable",
  }));
  return {
    ...report,
    report_kind: "aarogya_bhadratha",
    filename: report?.bill?.filename || "Aarogya Bhadratha report",
    hospital: {
      name_from_bill: report?.hospital?.ocr_hospital_name || matched.name || null,
    },
    comparison_settings: {
      city: matched.district || "",
      state_name: patient?.state || "Telangana",
      comparison_scheme: "aarogya_bhadratha",
    },
    patient: {
      id: patient?.id || null,
      name: patient?.name || report?.patient?.name || null,
    },
    line_items: lineItems,
    comparedAt: new Date().toISOString(),
  };
}

export async function getReport(reportId) {
  return request(`${BASE}/reports/${reportId}`);
}
