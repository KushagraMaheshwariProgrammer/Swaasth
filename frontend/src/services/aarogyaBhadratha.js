import { getApiBase } from "./apiBase";

function aarogyaBase() {
  return `${getApiBase()}/api/aarogya-bhadratha`;
}

const HOSPITAL_SEARCH_STOP = new Set([
  "hospital",
  "hospitals",
  "hosp",
  "medical",
  "centre",
  "center",
  "pvt",
  "ltd",
  "limited",
  "the",
  "and",
  "of",
  "a",
  "unit",
  "care",
  "super",
  "speciality",
  "specialty",
  "multi",
  "private",
]);

/** Build a forgiving search query from a bill OCR hospital name. */
export function buildHospitalSearchQuery(name) {
  const raw = String(name || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean);
  let tokens = raw.filter(
    (token) => token.length >= 3 && !HOSPITAL_SEARCH_STOP.has(token)
  );
  if (!tokens.length) {
    tokens = raw.filter((token) => token.length >= 2);
  }
  if (tokens.length) {
    return tokens.slice(0, 4).join(" ");
  }
  return String(name || "").trim();
}

/** True when a directory result looks like the same brand as the bill hospital. */
export function isSameHospitalBrand(billName, hospital) {
  const billTokens = buildHospitalSearchQuery(billName)
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  if (!billTokens.length) {
    return false;
  }
  const hay = `${hospital?.name || ""} ${hospital?.full_name || ""}`.toLowerCase();
  return billTokens.every((token) => hay.includes(token));
}

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
  return request(`${getApiBase()}/api/aarogya-bhadratha/extract-bill`, {
    method: "POST",
    body: formData,
  });
}

export async function verifyHospital({ hospitalName, district = "", address = "" }) {
  return request(`${aarogyaBase()}/verify-hospital`, {
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
  return request(`${aarogyaBase()}/compare-rates`, {
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
  return request(`${aarogyaBase()}/hospitals/search?${params}`);
}

export async function getDistricts() {
  return request(`${aarogyaBase()}/districts`);
}

export async function getSpecialities() {
  return request(`${aarogyaBase()}/specialities`);
}

export async function getAarogyaStatus() {
  return request(`${aarogyaBase()}/status`);
}

export function reportPdfUrl(reportId) {
  return `${aarogyaBase()}/reports/${reportId}/pdf`;
}

// Render the report PDF from the full client-held report object so it works
// for both freshly generated and reopened (history) reports.
export {
  openReportPdf,
  downloadReportPdf,
  shareReportPdf,
} from "./reportPdf";

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
  return request(`${aarogyaBase()}/reports/${reportId}`);
}
