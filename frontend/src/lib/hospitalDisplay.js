/** User-facing hospital location and label formatting. */

function toTitleCaseWord(word) {
  if (!word) {
    return "";
  }
  if (word.length <= 4 && word === word.toUpperCase()) {
    return word;
  }
  return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
}

export function toTitleCase(text) {
  return String(text || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map(toTitleCaseWord)
    .join(" ");
}

export function formatDisplayName(text) {
  const trimmed = String(text || "").trim();
  if (!trimmed) {
    return "";
  }
  if (trimmed === trimmed.toUpperCase() && /[A-Z]/.test(trimmed)) {
    return toTitleCase(trimmed);
  }
  return trimmed;
}

/**
 * Format city, district, and state without duplicates or all-caps clutter.
 * Example: HYDERABAD, HYDERABAD, TELANGANA -> Hyderabad, Telangana
 */
export function formatHospitalLocation(city, district, state) {
  const parts = [city, district, state]
    .map((part) => String(part || "").trim())
    .filter(Boolean)
    .map(toTitleCase);

  const unique = [];
  const seen = new Set();
  for (const part of parts) {
    const key = part.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    unique.push(part);
  }
  return unique.join(", ");
}

export function formatHospitalTypeBadge(hospitalType) {
  const text = formatDisplayName(hospitalType);
  if (!text) {
    return "Unknown";
  }
  return text;
}

export function formatEmpanelmentStatusLabel(status) {
  const text = String(status || "").trim().toLowerCase();
  if (!text) {
    return "Unknown";
  }
  if (text === "active" || text === "empanelled") {
    return "Active";
  }
  if (text === "suspended") {
    return "Suspended";
  }
  if (text === "delisted") {
    return "Delisted";
  }
  return toTitleCase(text.replaceAll("_", " "));
}

export function hospitalTypeBadgeClass(hospitalType) {
  const text = String(hospitalType || "").toLowerCase();
  if (text.includes("public") || text.includes("government")) {
    return "hospital-type-badge hospital-type-public";
  }
  if (text.includes("private")) {
    return "hospital-type-badge hospital-type-private";
  }
  return "hospital-type-badge hospital-type-neutral";
}

export function empanelmentStatusBadgeClass(status) {
  const text = String(status || "").toLowerCase();
  if (text === "active" || text === "empanelled") {
    return "empanelment-status-badge empanelment-status-active";
  }
  if (text === "suspended") {
    return "empanelment-status-badge empanelment-status-suspended";
  }
  if (text === "delisted") {
    return "empanelment-status-badge empanelment-status-delisted";
  }
  return "empanelment-status-badge empanelment-status-neutral";
}
