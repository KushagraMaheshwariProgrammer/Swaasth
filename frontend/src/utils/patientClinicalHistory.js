import { normalizeClinicalHistory } from "./clinicalHistory";
import { getBillSortTime } from "../services/bills";
import { getPatientBills } from "../services/patients";
import { getPatientHistoricalDocuments } from "../services/patientHistoricalDocuments";
import { canSaveMedicalHistory } from "./medicalHistoryConsent";

const MAX_PRIOR_REPORTS = 10;

function reportDate(bill) {
  const timestamp = getBillSortTime(bill);
  if (timestamp) {
    return new Date(timestamp).toISOString().slice(0, 10);
  }
  return bill?.bill_date || bill?.comparedAt || null;
}

function mapPriorReport(bill) {
  const clinicalContext = bill?.clinical_context || {};
  const prescription = bill?.prescription || {};
  return {
    date: reportDate(bill),
    diagnosis:
      bill?.diagnosis ||
      prescription?.diagnosis ||
      clinicalContext?.diagnosis ||
      "",
    symptoms: clinicalContext?.symptoms || [],
    test_results: clinicalContext?.test_results || [],
    medicines:
      prescription?.medicines?.map((item) => item?.name).filter(Boolean) ||
      bill?.prescription_medicines?.map((item) => item?.name).filter(Boolean) ||
      [],
    source: "saved_report",
  };
}

function mapLegacyDocument(doc) {
  return {
    documentDate: doc.documentDate,
    documentType: doc.documentType,
    extractedSummary: doc.extractedSummary || {},
    source: "legacy_document",
  };
}

export async function buildPatientHistoryPayload(
  userId,
  patient,
  options = {}
) {
  const accountConsent = options.accountConsent || {};
  const profile = normalizeClinicalHistory(patient?.clinicalHistory);

  const payload = {
    profile,
    prior_reports: [],
    legacy_documents: [],
  };

  if (!patient) {
    return payload;
  }

  const consentAllows = canSaveMedicalHistory(accountConsent, patient);

  if (consentAllows && userId && patient.id) {
    const [bills, legacyDocs] = await Promise.all([
      getPatientBills(userId, patient.id),
      getPatientHistoricalDocuments(userId, patient.id),
    ]);

    payload.prior_reports = [...bills]
      .sort((left, right) => getBillSortTime(right) - getBillSortTime(left))
      .slice(0, options.maxReports || MAX_PRIOR_REPORTS)
      .map(mapPriorReport)
      .filter(
        (report) =>
          report.diagnosis ||
          report.symptoms?.length ||
          report.test_results?.length ||
          report.medicines?.length
      );

    payload.legacy_documents = legacyDocs.map(mapLegacyDocument);
  }

  return payload;
}
