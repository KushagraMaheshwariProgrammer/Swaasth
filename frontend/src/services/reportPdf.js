import { Capacitor } from "@capacitor/core";
import { resolveActionPlan } from "../actionPlanUtils";
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

async function postRenderPdf(payload) {
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

export async function fetchReportPdfBlob(report) {
  return postRenderPdf(prepareReportForPdf(report));
}

/** Request the guardrailed dispute-pack PDF for a report. */
export async function fetchDisputePackPdfBlob(report) {
  return postRenderPdf({
    ...prepareReportForPdf(report),
    report_kind: "dispute_pack",
    action_plan: resolveActionPlan(report),
  });
}

function buildPdfFile(blob, filename) {
  if (typeof File === "undefined") {
    return null;
  }
  return new File([blob], filename, { type: "application/pdf" });
}

function triggerAnchorDownload(blobUrl, filename) {
  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

function prefersNativeFileShare() {
  return Capacitor.isNativePlatform() || /Android|iPhone|iPad/i.test(navigator.userAgent);
}

async function sharePdfFile(blob, filename, reportTitle) {
  const file = buildPdfFile(blob, filename);
  if (!file || typeof navigator.share !== "function") {
    return false;
  }

  const sharePayload = {
    title: reportTitle,
    text: reportTitle,
    files: [file],
  };

  if (navigator.canShare && !navigator.canShare(sharePayload)) {
    return false;
  }

  await navigator.share(sharePayload);
  return true;
}

export async function loadReportPdfBlobUrl(report) {
  const blob = await fetchReportPdfBlob(report);
  return {
    blob,
    blobUrl: URL.createObjectURL(blob),
    filename: buildReportFilename(report),
    title: resolveReportMeta(report).reportTitle,
  };
}

export function revokeReportPdfBlobUrl(blobUrl) {
  if (blobUrl) {
    URL.revokeObjectURL(blobUrl);
  }
}

export async function downloadReportPdf(report, filename, blobOverride = null) {
  const blob = blobOverride || (await fetchReportPdfBlob(report));
  const name = filename || buildReportFilename(report);
  const reportTitle = resolveReportMeta(report).reportTitle;

  if (prefersNativeFileShare()) {
    try {
      const shared = await sharePdfFile(blob, name, reportTitle);
      if (shared) {
        return { method: "share" };
      }
    } catch (error) {
      if (error?.name === "AbortError") {
        return { method: "cancelled" };
      }
    }
  }

  const blobUrl = URL.createObjectURL(blob);
  try {
    triggerAnchorDownload(blobUrl, name);
    return { method: "download" };
  } finally {
    window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
  }
}

export function buildDisputePackFilename(report) {
  const patientName = (report?.patient?.name || "report").replace(/\s+/g, "-");
  return `dispute-pack-${patientName}.pdf`;
}

export async function downloadDisputePackPdf(report) {
  const blob = await fetchDisputePackPdfBlob(report);
  const name = buildDisputePackFilename(report);
  const reportTitle = "Dispute Pack — Factual Summary";

  if (prefersNativeFileShare()) {
    try {
      const shared = await sharePdfFile(blob, name, reportTitle);
      if (shared) {
        return { method: "share" };
      }
    } catch (error) {
      if (error?.name === "AbortError") {
        return { method: "cancelled" };
      }
    }
  }

  const blobUrl = URL.createObjectURL(blob);
  try {
    triggerAnchorDownload(blobUrl, name);
    return { method: "download" };
  } finally {
    window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
  }
}

export async function shareReportPdf(report, blobOverride = null) {
  const reportMeta = resolveReportMeta(report);
  const filename = buildReportFilename(report);
  const blob = blobOverride || (await fetchReportPdfBlob(report));

  try {
    const shared = await sharePdfFile(blob, filename, reportMeta.reportTitle);
    if (shared) {
      return { shared: true, method: "file" };
    }
  } catch (error) {
    if (error?.name === "AbortError") {
      return { shared: false, cancelled: true };
    }
    throw error;
  }

  if (typeof navigator.share === "function") {
    const textPayload = {
      title: reportMeta.reportTitle,
      text: reportMeta.reportTitle,
    };
    if (!navigator.canShare || navigator.canShare(textPayload)) {
      await navigator.share(textPayload);
      return { shared: true, method: "text" };
    }
  }

  return { shared: false };
}
