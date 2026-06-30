import { getApiBase } from "./apiBase";
import { buildReportFilename, resolveReportMeta } from "../data/reportExport";
import { backendUnreachableMessage, fetchBackend } from "./httpUtils";

function isFirestoreTimestamp(value) {
  return (
    value &&
    typeof value === "object" &&
    (typeof value.toDate === "function" ||
      (typeof value.seconds === "number" && typeof value.nanoseconds === "number"))
  );
}

function normalizeForJson(value) {
  if (value === undefined) {
    return undefined;
  }
  if (value === null || typeof value !== "object") {
    return value;
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  if (isFirestoreTimestamp(value)) {
    return typeof value.toDate === "function"
      ? value.toDate().toISOString()
      : new Date(value.seconds * 1000).toISOString();
  }
  if (Array.isArray(value)) {
    return value.map((item) => normalizeForJson(item));
  }
  const normalized = {};
  for (const [key, nested] of Object.entries(value)) {
    const next = normalizeForJson(nested);
    if (next !== undefined) {
      normalized[key] = next;
    }
  }
  return normalized;
}

/** Strip non-JSON-safe values before POSTing the report to the PDF endpoint. */
export function prepareReportForPdf(report) {
  if (!report || typeof report !== "object") {
    throw new Error("No report data to export.");
  }
  const cleaned = normalizeForJson(report);
  if (typeof cleaned.ocr_text === "string" && cleaned.ocr_text.length > 100_000) {
    cleaned.ocr_text = cleaned.ocr_text.slice(0, 100_000);
  }
  return cleaned;
}

function openPreviewWindow() {
  const preview = window.open("about:blank", "_blank", "noopener,noreferrer");
  if (!preview) {
    throw new Error("Pop-up blocked. Allow pop-ups for this site and try again.");
  }
  return preview;
}

async function fetchReportPdfBlob(report) {
  const payload = prepareReportForPdf(report);
  let response;
  try {
    response = await fetchBackend(`${getApiBase()}/api/reports/render-pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    if (error?.message === "Failed to fetch" || error?.name === "TypeError") {
      throw new Error(backendUnreachableMessage());
    }
    throw error;
  }

  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      detail = body?.detail;
    } catch {
      detail = "";
    }
    if (detail) {
      throw new Error(
        Array.isArray(detail) ? detail.map((entry) => entry.msg).join(", ") : detail
      );
    }
    if (response.status >= 502 && response.status <= 504) {
      throw new Error(backendUnreachableMessage());
    }
    throw new Error("Could not generate the report PDF.");
  }

  return response.blob();
}

export async function openReportPdf(report) {
  const preview = openPreviewWindow();
  try {
    const blob = await fetchReportPdfBlob(report);
    const blobUrl = URL.createObjectURL(blob);
    preview.location.replace(blobUrl);
  } catch (error) {
    preview.close();
    throw error;
  }
}

export async function downloadReportPdf(report, filename) {
  const blob = await fetchReportPdfBlob(report);
  const blobUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = filename || buildReportFilename(report);
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
}

export async function shareReportPdf(report) {
  const reportMeta = resolveReportMeta(report);
  const filename = buildReportFilename(report);
  const blob = await fetchReportPdfBlob(report);
  const file =
    typeof File !== "undefined"
      ? new File([blob], filename, { type: "application/pdf" })
      : null;

  if (file && navigator.canShare?.({ files: [file] }) && navigator.share) {
    try {
      await navigator.share({
        title: reportMeta.reportTitle,
        text: reportMeta.reportTitle,
        files: [file],
      });
      return true;
    } catch (error) {
      if (error?.name === "AbortError") {
        return false;
      }
    }
  }

  const preview = openPreviewWindow();
  const blobUrl = URL.createObjectURL(blob);
  preview.location.replace(blobUrl);
  return false;
}
