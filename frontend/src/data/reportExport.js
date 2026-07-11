/**
 * Report metadata for PDF export, sharing, and history labels.
 */

const REPORT_META = {
  general: {
    id: "general",
    label: "Bill review",
    reportTitle: "Bill Review Report",
    filenamePrefix: "bill",
  },
  bill: {
    id: "bill",
    label: "Bill review",
    reportTitle: "Bill Review Report",
    filenamePrefix: "bill",
  },
  prescription: {
    id: "prescription",
    label: "Prescription review",
    reportTitle: "Prescription Treatment Appropriateness Report",
    filenamePrefix: "prescription",
  },
  clinical: {
    id: "clinical",
    label: "Clinical review",
    reportTitle: "Clinical Diagnosis Support Report",
    filenamePrefix: "clinical",
  },
  combined: {
    id: "combined",
    label: "Bill + prescription review",
    reportTitle: "Bill and Prescription Review Report",
    filenamePrefix: "bill-prescription",
  },
  medical_history: {
    id: "medical_history",
    label: "Medical history",
    reportTitle: "Medical History Summary",
    filenamePrefix: "medical-history",
  },
};

const REPORT_META_BY_ID = Object.fromEntries(
  Object.values(REPORT_META).map((entry) => [entry.id, entry])
);

export function resolveReportMeta(report) {
  const reportKind = report?.report_kind;
  if (reportKind && REPORT_META_BY_ID[reportKind]) {
    return REPORT_META_BY_ID[reportKind];
  }

  if (reportKind === "bundle") {
    return {
      id: "bundle",
      label: "Document bundle",
      reportTitle: "Document Bundle Report",
      filenamePrefix: "bundle",
    };
  }

  if (report?.treatment_audit_flags && !report?.line_items?.length) {
    return report?.report_kind === "clinical"
      ? REPORT_META.clinical
      : REPORT_META.prescription;
  }

  return REPORT_META.general;
}

export function reportKindLabel(report) {
  if (report?.report_kind === "bundle") {
    const count = report.source_documents?.length || 0;
    return count ? `${count} documents` : "Document bundle";
  }
  if (report?.report_kind === "prescription") {
    return "Prescription review";
  }
  if (report?.report_kind === "clinical") {
    return "Clinical review";
  }
  if (report?.report_kind === "combined") {
    return "Bill + prescription review";
  }
  if (report?.line_items?.length) {
    return `${report.line_items.length} items`;
  }
  return resolveReportMeta(report).label;
}

export function hasBillReportContent(report) {
  return Boolean(report?.line_items?.length);
}

export function hasPrescriptionReportContent(report) {
  if (!report) {
    return false;
  }
  return Boolean(
    report.treatment_audit_flags ||
      report.restricted_medicine_flags?.length ||
      (report.patient_questions || []).length
  );
}

/** Which results panel to render for a saved or live report payload. */
export function resolveResultsView(report) {
  if (hasBillReportContent(report)) {
    return "bill";
  }
  if (hasPrescriptionReportContent(report)) {
    return "prescription";
  }
  return null;
}

export function canExportReport(report) {
  return Boolean(resolveResultsView(report));
}

export function buildReportFilename(report) {
  const meta = resolveReportMeta(report);
  const patientName = (report?.patient?.name || "report").replace(/\s+/g, "-");
  return `${meta.filenamePrefix}-${patientName}.pdf`;
}
