/**
 * Registry of bill comparison schemes supported by the app.
 *
 * To add a new scheme:
 * 1. Register its HTML renderer on the backend in `report_pdf.py`.
 * 2. Add an entry here with label/title/filename metadata.
 * 3. Ensure saved bills set `comparison_settings.comparison_scheme` or
 *    `report_kind` to the scheme id.
 */

export const SCHEMES = {
  cghs: {
    id: "cghs",
    label: "CGHS Benchmark",
    reportTitle: "CGHS Bill Comparison Report",
    filenamePrefix: "cghs",
  },
  hbp_pmjay: {
    id: "hbp_pmjay",
    label: "PM-JAY HBP 2022 Benchmark",
    reportTitle: "PM-JAY HBP Bill Comparison Report",
    filenamePrefix: "pmjay-hbp",
  },
  aarogya_bhadratha: {
    id: "aarogya_bhadratha",
    label: "Aarogya Bhadratha Scheme",
    reportTitle: "Aarogya Bhadratha Bill Comparison Report",
    filenamePrefix: "aarogya-bhadratha",
  },
};

const SCHEME_BY_ID = Object.fromEntries(
  Object.values(SCHEMES).map((scheme) => [scheme.id, scheme])
);

/**
 * Resolve scheme metadata from a saved or live report object.
 */
export function resolveScheme(report) {
  const reportKind = report?.report_kind;
  if (reportKind && SCHEME_BY_ID[reportKind]) {
    return SCHEME_BY_ID[reportKind];
  }

  const comparisonScheme = report?.comparison_settings?.comparison_scheme;
  if (comparisonScheme && SCHEME_BY_ID[comparisonScheme]) {
    return SCHEME_BY_ID[comparisonScheme];
  }

  return SCHEMES.cghs;
}

/**
 * Whether the report has enough data to export as a PDF.
 */
export function canExportReport(report) {
  if (!report) {
    return false;
  }
  if (report.report_kind === "aarogya_bhadratha") {
    return Boolean(report.comparison?.items?.length);
  }
  return Boolean(report.line_items?.length);
}

export function buildReportFilename(report) {
  const scheme = resolveScheme(report);
  const patientName = (report?.patient?.name || "report").replace(/\s+/g, "-");
  return `${scheme.filenamePrefix}-${patientName}.pdf`;
}
