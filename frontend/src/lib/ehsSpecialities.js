/** EHS/JHS hospital speciality display — never show raw S1/M1 codes in UI. */

const CODE_PREFIX = /^[MS]\d+\s*[-–—:]\s*/i;

export function stripSpecialityCodePrefix(label) {
  return String(label || "")
    .replace(CODE_PREFIX, "")
    .trim();
}

export function formatEhsSpecialitiesForDisplay(hospitalVerification = {}) {
  const readable = hospitalVerification?.specialities_readable;
  if (Array.isArray(readable) && readable.length) {
    const names = readable
      .map(stripSpecialityCodePrefix)
      .filter(Boolean)
      .filter((name, index, list) => list.indexOf(name) === index);
    if (names.length) {
      return {
        hasSpecialities: true,
        cardLine: "Specialities: Available",
        detailsText: names.join(", "),
      };
    }
  }

  const raw = hospitalVerification?.specialities;
  if (!raw) {
    return {
      hasSpecialities: false,
      cardLine: null,
      detailsText: null,
    };
  }

  const tokens = String(raw)
    .split(/[,;|]/)
    .map(stripSpecialityCodePrefix)
    .filter(Boolean);

  if (!tokens.length) {
    return {
      hasSpecialities: true,
      cardLine: "Specialities available — verify with hospital/helpdesk",
      detailsText: "Specialities available — verify with hospital/helpdesk",
    };
  }

  return {
    hasSpecialities: true,
    cardLine: "Specialities: Available",
    detailsText: tokens.join(", "),
  };
}
