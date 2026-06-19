import { useEffect, useState } from "react";

export const HOSPITAL_TYPE_OPTIONS = [
  { id: "general", label: "General hospital" },
  { id: "speciality", label: "Speciality hospital" },
];

export const formatCurrency = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "--";
  }
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value));
};

export const getFlagMeta = (flag) => {
  if (flag === "overpriced") {
    return {
      badgeLabel: "Overpriced",
      badgeClass: "status-pill status-red",
      cardClass: "result-card result-overpriced",
    };
  }
  if (flag === "acceptable") {
    return {
      badgeLabel: "Acceptable",
      badgeClass: "status-pill status-green",
      cardClass: "result-card result-acceptable",
    };
  }
  return {
    badgeLabel: "No Data",
    badgeClass: "status-pill status-neutral",
    cardClass: "result-card result-neutral",
  };
};

export const getAuditSeverityMeta = (severity) => {
  if (severity === "HIGH") {
    return {
      badgeLabel: "High",
      badgeClass: "status-pill status-red",
      cardClass: "audit-flag-card audit-flag-high",
    };
  }
  if (severity === "MEDIUM") {
    return {
      badgeLabel: "Medium",
      badgeClass: "status-pill status-amber",
      cardClass: "audit-flag-card audit-flag-medium",
    };
  }
  return {
    badgeLabel: "Low",
    badgeClass: "status-pill status-neutral",
    cardClass: "audit-flag-card audit-flag-low",
  };
};

export const getAuditRiskMeta = (riskLevel) => {
  if (riskLevel === "HIGH") {
    return { label: "High Risk", className: "audit-risk audit-risk-high" };
  }
  if (riskLevel === "MEDIUM") {
    return { label: "Medium Risk", className: "audit-risk audit-risk-medium" };
  }
  return { label: "Low Risk", className: "audit-risk audit-risk-low" };
};

export function getBillComparisonScheme(patient, comparisonSettings = null) {
  if (comparisonSettings?.comparison_scheme) {
    return comparisonSettings.comparison_scheme;
  }
  if (patient?.rajivAarogyasriSelected) {
    return "rajiv_aarogyasri";
  }
  if (patient?.ayushmanEligible) {
    return "hbp_pmjay";
  }
  return "cghs";
}

export function getComparisonSchemeCopy(scheme) {
  if (scheme === "rajiv_aarogyasri") {
    return {
      compareButton: "Compare with Aarogyasri package rates →",
      loading: "Comparing with Aarogyasri package rates...",
      editHint:
        "Correct anything the scan missed, then compare against approved Aarogyasri package rates.",
      rateLabel: "Aarogyasri Package Rate",
      benchmarkLabel: "Rajiv Aarogyasri package benchmark",
    };
  }
  if (scheme === "hbp_pmjay") {
    return {
      compareButton: "Compare with PM-JAY HBP →",
      loading: "Comparing with Ayushman Bharat HBP 2022 rates...",
      editHint:
        "Correct anything the scan missed, then compare against PM-JAY HBP rates.",
      rateLabel: "PM-JAY HBP Rate",
      benchmarkLabel: "PM-JAY HBP 2022 benchmark",
    };
  }
  return {
    compareButton: "Compare with CGHS →",
    loading: "Comparing with CGHS rates...",
    editHint: "Correct anything the scan missed, then compare against CGHS rates.",
    rateLabel: "CGHS Rate",
    benchmarkLabel: "CGHS benchmark",
  };
}

export function CountUp({ value, isCurrency = false, duration = 1200 }) {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    let frameId;
    let startTime;
    const target = Number(value) || 0;

    const tick = (now) => {
      if (!startTime) {
        startTime = now;
      }
      const progress = Math.min((now - startTime) / duration, 1);
      setDisplayValue(target * progress);
      if (progress < 1) {
        frameId = window.requestAnimationFrame(tick);
      }
    };

    frameId = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frameId);
  }, [duration, value]);

  return isCurrency ? formatCurrency(displayValue) : Math.round(displayValue);
}

export function computeBillSummary(result) {
  const lineItems = result?.line_items ?? [];
  return lineItems.reduce(
    (acc, item) => {
      const charged = Number(item.total_price ?? 0) || 0;
      const diff = Number(item.price_difference ?? 0) || 0;
      return {
        totalCharged: acc.totalCharged + charged,
        totalOvercharged: acc.totalOvercharged + Math.max(diff, 0),
        itemsFlagged: acc.itemsFlagged + (item.flag === "overpriced" ? 1 : 0),
      };
    },
    { totalCharged: 0, totalOvercharged: 0, itemsFlagged: 0 }
  );
}

export function buildPatientNameMap(patients) {
  const map = {};
  for (const patient of patients || []) {
    const name = patient?.name?.trim();
    if (!name) {
      continue;
    }
    for (const id of [patient.id, patient.localId, patient.firestoreId]) {
      if (id) {
        map[id] = name;
      }
    }
  }
  return map;
}

export function getBillPatientName(bill, patientNameById = {}) {
  const fromBill = bill?.patient?.name?.trim();
  if (fromBill) {
    return fromBill;
  }
  const patientId = bill?.patientId || bill?.patient?.id;
  if (patientId && patientNameById[patientId]) {
    return patientNameById[patientId];
  }
  return null;
}
