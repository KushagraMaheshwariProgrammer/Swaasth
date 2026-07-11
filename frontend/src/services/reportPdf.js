import { Capacitor } from "@capacitor/core";
import { Directory, Filesystem } from "@capacitor/filesystem";
import { Share } from "@capacitor/share";
import { resolveActionPlan } from "../actionPlanUtils";
import { getApiBase } from "./apiBase";
import { buildReportFilename, resolveReportMeta } from "../data/reportExport";
import {
  backendUnreachableMessage,
  extractApiErrorMessage,
  fetchBackend,
} from "./httpUtils";

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
export function prepareReportForPdf(report, exportOptions = null) {
  if (!report || typeof report !== "object") {
    throw new Error("No report data to export.");
  }
  const cleaned = normalizeForJson(report);
  const opts = exportOptions || report.export_options || {};
  cleaned.export_options = {
    include_stg_excerpts: opts.include_stg_excerpts !== false,
    include_legal_pathways: opts.include_legal_pathways !== false,
  };
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
    let payload = null;
    let text = "";
    try {
      text = await response.text();
      if (text.trim()) {
        payload = JSON.parse(text);
      }
    } catch {
      payload = null;
    }
    if (response.status >= 502 && response.status <= 504) {
      throw new Error(backendUnreachableMessage());
    }
    throw new Error(
      extractApiErrorMessage(payload, text, response, "Could not generate the report PDF.")
    );
  }

  return response.blob();
}

export async function fetchReportPdfBlob(report, exportOptions = null) {
  return postRenderPdf(prepareReportForPdf(report, exportOptions));
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

function isShareCancelled(error) {
  const message = String(error?.message || "").toLowerCase();
  return (
    error?.name === "AbortError" ||
    message.includes("cancel") ||
    message.includes("dismiss")
  );
}

function sanitizePdfFilename(filename) {
  return String(filename || "report.pdf").replace(/[^a-zA-Z0-9._-]/g, "_");
}

async function blobToBase64(blob) {
  const buffer = await blob.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 1) {
    binary += String.fromCharCode(bytes[index]);
  }
  return btoa(binary);
}

async function writePdfToNativeCache(blob, filename) {
  const { uri } = await Filesystem.writeFile({
    path: sanitizePdfFilename(filename),
    data: await blobToBase64(blob),
    directory: Directory.Cache,
  });
  return uri;
}

async function sharePdfViaCapacitor(blob, filename, reportTitle, dialogTitle) {
  if (!Capacitor.isNativePlatform()) {
    return false;
  }

  const uri = await writePdfToNativeCache(blob, filename);
  await Share.share({
    title: reportTitle,
    text: reportTitle,
    files: [uri],
    dialogTitle,
  });
  return true;
}

async function sharePdfFile(blob, filename, reportTitle) {
  if (Capacitor.isNativePlatform()) {
    return sharePdfViaCapacitor(blob, filename, reportTitle, "Share PDF");
  }

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

export async function loadReportPdfBlobUrl(report, exportOptions = null) {
  const blob = await fetchReportPdfBlob(report, exportOptions);
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

  if (Capacitor.isNativePlatform()) {
    try {
      const shared = await sharePdfViaCapacitor(blob, name, reportTitle, "Save PDF");
      if (shared) {
        return { method: "share" };
      }
    } catch (error) {
      if (isShareCancelled(error)) {
        return { method: "cancelled" };
      }
      throw error;
    }
    return { method: "needsPreview" };
  } else if (prefersNativeFileShare()) {
    try {
      const shared = await sharePdfFile(blob, name, reportTitle);
      if (shared) {
        return { method: "share" };
      }
    } catch (error) {
      if (isShareCancelled(error)) {
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

  if (Capacitor.isNativePlatform()) {
    try {
      const shared = await sharePdfViaCapacitor(blob, name, reportTitle, "Save PDF");
      if (shared) {
        return { method: "share" };
      }
    } catch (error) {
      if (isShareCancelled(error)) {
        return { method: "cancelled" };
      }
      throw error;
    }
    return { method: "needsPreview" };
  } else if (prefersNativeFileShare()) {
    try {
      const shared = await sharePdfFile(blob, name, reportTitle);
      if (shared) {
        return { method: "share" };
      }
    } catch (error) {
      if (isShareCancelled(error)) {
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
    if (isShareCancelled(error)) {
      return { shared: false, cancelled: true };
    }
    throw error;
  }

  if (!Capacitor.isNativePlatform() && typeof navigator.share === "function") {
    const textPayload = {
      title: reportMeta.reportTitle,
      text: reportMeta.reportTitle,
    };
    if (!navigator.canShare || navigator.canShare(textPayload)) {
      await navigator.share(textPayload);
      return { shared: true, method: "text" };
    }
  }

  return { shared: false, needsPreview: true };
}
