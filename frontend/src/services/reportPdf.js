import { getApiBase } from "./apiBase";
import { buildReportFilename, resolveScheme } from "../data/schemes";
import { backendUnreachableMessage } from "./httpUtils";

async function fetchReportPdfBlob(report) {
  let response;
  try {
    response = await fetch(`${getApiBase()}/api/reports/render-pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(report),
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
      const payload = await response.json();
      detail = payload?.detail;
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
  const blob = await fetchReportPdfBlob(report);
  const blobUrl = URL.createObjectURL(blob);
  window.open(blobUrl, "_blank", "noopener");
}

export async function downloadReportPdf(report, filename) {
  const blob = await fetchReportPdfBlob(report);
  const blobUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = filename || buildReportFilename(report);
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(blobUrl);
}

export async function shareReportPdf(report) {
  const scheme = resolveScheme(report);
  const filename = buildReportFilename(report);
  const blob = await fetchReportPdfBlob(report);
  const file =
    typeof File !== "undefined"
      ? new File([blob], filename, { type: "application/pdf" })
      : null;

  if (file && navigator.canShare?.({ files: [file] }) && navigator.share) {
    try {
      await navigator.share({
        title: scheme.reportTitle,
        text: scheme.reportTitle,
        files: [file],
      });
      return true;
    } catch (error) {
      if (error?.name === "AbortError") {
        return false;
      }
    }
  }

  const blobUrl = URL.createObjectURL(blob);
  window.open(blobUrl, "_blank", "noopener");
  return false;
}
