/** PM-JAY speciality display helpers — codes stay internal, never shown raw in UI. */

const PMJAY_SPECIALITY_NAMES = {
  M1: "General Medicine",
  M2: "General Surgery",
  M3: "Obstetrics & Gynaecology",
  M4: "Paediatrics",
  M5: "Anaesthesiology",
  M6: "ENT",
  M7: "Ophthalmology",
  M8: "Dental",
  S1: "Cardiology",
  S2: "Cardiothoracic Surgery",
  S3: "Neurology",
  S4: "Neuro Surgery",
  S5: "Urology",
  S6: "Nephrology",
  S7: "Medical Oncology",
  S8: "Surgical Oncology",
  S9: "Radiation Oncology",
  S10: "Gastroenterology",
  S11: "Plastic Surgery",
  S12: "Pulmonology",
  S13: "Critical Care",
  S14: "Interventional Radiology",
  S15: "Rheumatology",
  S16: "Endocrinology",
};

const RAW_CODE_PATTERN = /^[MS]\d+$/i;

export function isRawSpecialityCode(token) {
  return RAW_CODE_PATTERN.test(String(token || "").trim());
}

function splitSpecialityTokens(raw) {
  if (!raw) {
    return [];
  }
  return String(raw)
    .split(/[,;|]/)
    .map((token) => token.trim())
    .filter(Boolean);
}

function mapTokenToReadableName(token) {
  const normalized = String(token || "").trim();
  if (!normalized) {
    return null;
  }
  if (isRawSpecialityCode(normalized)) {
    return PMJAY_SPECIALITY_NAMES[normalized.toUpperCase()] || null;
  }
  if (RAW_CODE_PATTERN.test(normalized.replace(/\s+/g, ""))) {
    return PMJAY_SPECIALITY_NAMES[normalized.toUpperCase().replace(/\s+/g, "")] || null;
  }
  return normalized;
}

/**
 * Convert raw speciality field to user-facing display data.
 * Never exposes M1/S8-style codes in returned strings.
 */
export function formatSpecialitiesForDisplay(raw) {
  const tokens = splitSpecialityTokens(raw);
  if (!tokens.length) {
    return {
      hasSpecialities: false,
      cardLine: null,
      chips: [],
      allReadable: [],
      detailsText: null,
    };
  }

  const readable = [];
  const seen = new Set();
  let sawRawCodes = false;

  for (const token of tokens) {
    if (isRawSpecialityCode(token)) {
      sawRawCodes = true;
    }
    const name = mapTokenToReadableName(token);
    if (!name || isRawSpecialityCode(name)) {
      continue;
    }
    const key = name.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    readable.push(name);
  }

  if (readable.length) {
    return {
      hasSpecialities: true,
      cardLine: "Specialities: Available",
      chips: readable.slice(0, 2),
      allReadable: readable,
      detailsText: readable.join(", "),
    };
  }

  if (sawRawCodes || tokens.some(isRawSpecialityCode)) {
    return {
      hasSpecialities: true,
      cardLine: "Specialities available — verify with hospital/helpdesk",
      chips: [],
      allReadable: [],
      detailsText:
        "Specialities available — verify with hospital/helpdesk",
    };
  }

  return {
    hasSpecialities: true,
    cardLine: "Specialities: Available",
    chips: tokens.slice(0, 2),
    allReadable: tokens,
    detailsText: tokens.join(", "),
  };
}
