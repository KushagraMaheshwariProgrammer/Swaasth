/** Normalize OCR/AI date strings to YYYY-MM-DD for HTML date inputs. */
export function normalizeToIsoDate(raw) {
  if (raw == null) {
    return "";
  }
  const value = String(raw).trim();
  if (!value) {
    return "";
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value;
  }

  const slashMatch = value.match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})$/);
  if (slashMatch) {
    let [, day, month, year] = slashMatch;
    if (year.length === 2) {
      year = Number(year) > 50 ? `19${year}` : `20${year}`;
    }
    const iso = `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
    if (!Number.isNaN(Date.parse(iso))) {
      return iso;
    }
  }

  const ymdMatch = value.match(/^(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})$/);
  if (ymdMatch) {
    const [, year, month, day] = ymdMatch;
    const iso = `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
    if (!Number.isNaN(Date.parse(iso))) {
      return iso;
    }
  }

  const parsed = Date.parse(value);
  if (!Number.isNaN(parsed)) {
    return new Date(parsed).toISOString().slice(0, 10);
  }

  return "";
}

/** Map an extraction API payload to a document date for a given type. */
export function detectDocumentDate(documentType, payload) {
  if (!payload) {
    return "";
  }
  switch (documentType) {
    case "prescription":
      return normalizeToIsoDate(payload.prescription_date);
    case "bill":
      return normalizeToIsoDate(payload.bill_date);
    case "lab_report":
      return normalizeToIsoDate(payload.report_date);
    case "discharge_summary":
      return normalizeToIsoDate(payload.discharge_date);
    case "preauth_letter":
      return normalizeToIsoDate(payload.authorization_date);
    default:
      return "";
  }
}

export function buildDatePromptItem({ id, filename, documentType, detectedDate = "" }) {
  return {
    id,
    filename: filename || "document",
    documentType,
    detectedDate: normalizeToIsoDate(detectedDate),
    documentDate: normalizeToIsoDate(detectedDate),
  };
}

export function itemsMissingDates(items) {
  return (items || []).filter((item) => !normalizeToIsoDate(item.documentDate));
}

export function applyConfirmedDates(items) {
  return (items || []).map((item) => ({
    ...item,
    documentDate: normalizeToIsoDate(item.documentDate),
  }));
}
