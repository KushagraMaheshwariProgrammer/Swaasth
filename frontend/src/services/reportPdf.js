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
import { confirmPhiExport } from "../utils/confirmPhiExport";

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

/** Strip non-JSON-safe values and raw OCR text before POSTing to the PDF endpoint. */
export function prepareReportForPdf(report, exportOptions = null) {
  if (!report || typeof report !== "object") {
    throw new Error("No report data to export.");
  }
  const cleaned = stripOcrFields(normalizeForJson(report));
  const opts = exportOptions || report.export_options || {};
  cleaned.export_options = {
    include_stg_excerpts: opts.include_stg_excerpts !== false,
    include_legal_pathways: opts.include_legal_pathways !== false,
  };
  return cleaned;
}

function stripOcrFields(value) {
  if (value === null || typeof value !== "object") {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => stripOcrFields(item));
  }
  const cleaned = {};
  for (const [key, nested] of Object.entries(value)) {
    if (key === "ocr_text" || key === "ocrText") {
      continue;
    }
    cleaned[key] = stripOcrFields(nested);
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
    if (response.status === 401) {
      throw new Error(
        extractApiErrorMessage(
          payload,
          text,
          response,
          "Sign in required to continue."
        )
      );
    }
    if (
      response.status >= 502 &&
      response.status <= 504 &&
      !(payload && typeof payload === "object")
    ) {
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

export async function writePdfToNativeCache(blob, filename) {
  const { uri } = await Filesystem.writeFile({
    path: sanitizePdfFilename(filename),
    data: await blobToBase64(blob),
    directory: Directory.Cache,
  });
  return uri;
}

/** Open a PDF on native via cache URI + system share/viewer (Android WebView cannot iframe blobs). */
export async function openNativePdfViewer(blob, filename, reportTitle) {
  const uri = await writePdfToNativeCache(blob, filename);
  try {
    await Share.share({
      title: reportTitle,
      text: reportTitle,
      files: [uri],
      dialogTitle: "Open report",
    });
    return { opened: true, method: "share" };
  } catch (error) {
    if (isShareCancelled(error)) {
      return { opened: false, cancelled: true };
    }
    throw error;
  }
}

async function savePdfToDevice(blob, filename) {
  const safeName = sanitizePdfFilename(filename);
  const base64 = await blobToBase64(blob);

  if (Capacitor.getPlatform() === "android") {
    try {
      await Filesystem.writeFile({
        path: `Download/${safeName}`,
        data: base64,
        directory: Directory.ExternalStorage,
      });
      return { path: `Download/${safeName}` };
    } catch {
      // Fall back to app Documents if external storage is unavailable.
    }
  }

  await Filesystem.writeFile({
    path: safeName,
    data: base64,
    directory: Directory.Documents,
  });
  return { path: safeName };
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

  if (Capacitor.isNativePlatform()) {
    const saved = await savePdfToDevice(blob, name);
    return { method: "download", ...saved };
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

  if (Capacitor.isNativePlatform()) {
    const saved = await savePdfToDevice(blob, name);
    return { method: "download", ...saved };
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
  if (
    !confirmPhiExport(
      "This will share medical information outside the app. Continue?"
    )
  ) {
    return { shared: false, cancelled: true };
  }

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
