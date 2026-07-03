import { getBillSortTime } from "../services/bills";
import { getPatientBills } from "../services/patients";
import { getPatientHistoricalDocuments } from "../services/patientHistoricalDocuments";
import { normalizeClinicalHistory } from "./clinicalHistory";
import { canSaveMedicalHistory } from "./medicalHistoryConsent";
import { documentTypeLabel } from "./documentBundle";
import { normalizeToIsoDate } from "./documentDates";
import { reportKindLabel } from "../data/reportExport";
import { formatPatientAge } from "./patientAge";
import { genderLabel } from "../components/PatientForm";

function reportEntryDate(bill) {
  const timestamp = getBillSortTime(bill);
  if (timestamp) {
    return new Date(timestamp).toISOString().slice(0, 10);
  }
  return normalizeToIsoDate(bill?.bill_date || bill?.comparedAt || "");
}

function summarizeSwaasthReport(bill) {
  const clinicalContext = bill?.clinical_context || {};
  const prescription = bill?.prescription || {};
  const diagnosis =
    bill?.diagnosis ||
    prescription?.diagnosis ||
    clinicalContext?.diagnosis ||
    "";
  const medicines =
    prescription?.medicines?.map((item) => item?.name).filter(Boolean) ||
    bill?.prescription_medicines?.map((item) => item?.name).filter(Boolean) ||
    [];
  const symptoms = clinicalContext?.symptoms || [];
  const testResults = clinicalContext?.test_results || [];
  const flagsCount =
    (bill?.audit_flags?.flags_count || 0) +
    (bill?.treatment_audit_flags?.flags_count || 0);

  return {
    diagnosis,
    medicines,
    symptoms: symptoms.map((item) => item?.name || item).filter(Boolean),
    test_results: testResults,
    report_kind: bill?.report_kind,
    report_kind_label: reportKindLabel(bill),
    flags_count: flagsCount,
    hospital:
      bill?.hospital_profile?.name ||
      bill?.hospital?.name_from_bill ||
      bill?.comparison_settings?.city ||
      "",
    hospital_city:
      bill?.hospital_profile?.city || bill?.comparison_settings?.city || "",
    hospital_state:
      bill?.hospital_profile?.state ||
      bill?.comparison_settings?.state_name ||
      bill?.comparison_settings?.state_ut_name ||
      "",
    filename: bill?.filename || "Swaasth report",
  };
}

function summarizeLegacyDocument(doc) {
  const summary = doc.extractedSummary || {};
  return {
    document_type: doc.documentType,
    document_type_label: documentTypeLabel(doc.documentType),
    filename: doc.filename,
    diagnosis: summary.diagnosis || "",
    symptoms: (summary.symptoms || []).map((item) => item?.name || item).filter(Boolean),
    test_results: summary.test_results || [],
    medicines: (summary.medicines || []).map((item) => item?.name || item).filter(Boolean),
    line_items: summary.line_items || [],
    hospital: doc.hospitalName || "",
    hospital_city: doc.hospitalCity || "",
    hospital_state: doc.hospitalState || "",
  };
}

function sortTimeline(entries) {
  return [...entries].sort((left, right) => {
    const leftTime = new Date(left.date || 0).getTime();
    const rightTime = new Date(right.date || 0).getTime();
    return rightTime - leftTime;
  });
}

export async function buildMedicalHistoryDossier(
  userId,
  patient,
  options = {}
) {
  const accountConsent = options.accountConsent || {};
  const includeSwaasthReports = options.includeSwaasthReports !== false;
  const profile = normalizeClinicalHistory(patient?.clinicalHistory);
  const timeline = [];

  const consentAllows = canSaveMedicalHistory(accountConsent, patient);

  if (consentAllows && userId && patient?.id) {
    const [bills, legacyDocs] = await Promise.all([
      includeSwaasthReports ? getPatientBills(userId, patient.id) : Promise.resolve([]),
      getPatientHistoricalDocuments(userId, patient.id),
    ]);

    for (const bill of bills) {
      const summary = summarizeSwaasthReport(bill);
      const hasContent =
        summary.diagnosis ||
        summary.medicines.length ||
        summary.symptoms.length ||
        summary.test_results.length;
      if (!hasContent) {
        continue;
      }
      timeline.push({
        kind: "swaasth_report",
        date: reportEntryDate(bill),
        title: summary.filename,
        ...summary,
      });
    }

    for (const doc of legacyDocs) {
      timeline.push({
        kind: "legacy_document",
        date: normalizeToIsoDate(doc.documentDate),
        title: doc.filename,
        ...summarizeLegacyDocument(doc),
      });
    }
  }

  return {
    report_kind: "medical_history",
    patient: {
      id: patient?.id || null,
      name: patient?.name || "Patient",
      age: patient?.age ?? null,
      birthYear: patient?.birthYear ?? null,
      age_label: formatPatientAge(patient),
      gender: patient?.gender || null,
      gender_label: genderLabel(patient?.gender),
    },
    profile,
    timeline: sortTimeline(timeline),
    include_swaasth_reports: includeSwaasthReports,
    generated_at: new Date().toISOString(),
    consent_provided: consentAllows,
  };
}

export function buildMedicalHistoryFilename(dossier) {
  const patientName = (dossier?.patient?.name || "patient").replace(/\s+/g, "-");
  return `medical-history-${patientName}.pdf`;
}
