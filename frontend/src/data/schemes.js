/**
 * Bill report metadata for PDF export and sharing.
 */

export const SCHEMES = {
  general: {
    id: "general",
    label: "General Bill Review",
    reportTitle: "Bill Review Report",
    filenamePrefix: "bill",
  },
  bill: {
    id: "bill",
    label: "General Bill Review",
    reportTitle: "Bill Review Report",
    filenamePrefix: "bill",
  },
  prescription: {
    id: "prescription",
    label: "Prescription Review",
    reportTitle: "Prescription Treatment Appropriateness Report",
    filenamePrefix: "prescription",
  },
};

const SCHEME_BY_ID = Object.fromEntries(
  Object.values(SCHEMES).map((scheme) => [scheme.id, scheme])
);

export function resolveScheme(report) {
  const reportKind = report?.report_kind;
  if (reportKind && SCHEME_BY_ID[reportKind]) {
    return SCHEME_BY_ID[reportKind];
  }

  const comparisonScheme = report?.comparison_settings?.comparison_scheme;
  if (comparisonScheme && SCHEME_BY_ID[comparisonScheme]) {
    return SCHEME_BY_ID[comparisonScheme];
  }

  return SCHEMES.general;
}

export function canExportReport(report) {
  if (!report) {
    return false;
  }
  if (report.report_kind === "prescription") {
    return Boolean(report.treatment_audit_flags);
  }
  return Boolean(report.line_items?.length);
}

export function buildReportFilename(report) {
  const scheme = resolveScheme(report);
  const patientName = (report?.patient?.name || "report").replace(/\s+/g, "-");
  return `${scheme.filenamePrefix}-${patientName}.pdf`;
}
