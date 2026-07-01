export function emptyClinicalHistory() {
  return {
    conditions: [],
    surgeries: [],
    allergies: [],
  };
}

function parseOptionalYear(value) {
  const trimmed = String(value ?? "").trim();
  if (!trimmed) {
    return null;
  }
  const year = Number(trimmed);
  return Number.isFinite(year) ? year : null;
}

function normalizeHistoryRows(items, fields) {
  if (!Array.isArray(items)) {
    return [];
  }
  const normalized = [];
  for (const item of items) {
    if (!item || typeof item !== "object") {
      continue;
    }
    const row = {};
    let hasValue = false;
    for (const field of fields) {
      const value = String(item[field] ?? "").trim();
      row[field] = value;
      if (value) {
        hasValue = true;
      }
    }
    if (!hasValue) {
      continue;
    }
    if (fields.includes("year")) {
      row.year = parseOptionalYear(row.year);
    }
    normalized.push(row);
  }
  return normalized;
}

export function normalizeClinicalHistory(history) {
  const source = history || emptyClinicalHistory();
  return {
    conditions: normalizeHistoryRows(source.conditions, ["name", "year", "status"]).map(
      (item) => ({
        name: item.name,
        year: item.year ?? null,
        status: item.status || null,
      })
    ),
    surgeries: normalizeHistoryRows(source.surgeries, ["name", "year"]).map((item) => ({
      name: item.name,
      year: item.year ?? null,
    })),
    allergies: normalizeHistoryRows(source.allergies, ["name", "reaction"]).map(
      (item) => ({
        name: item.name,
        reaction: item.reaction || null,
      })
    ),
  };
}

export function clinicalHistorySummary(history) {
  const normalized = normalizeClinicalHistory(history);
  const parts = [];
  if (normalized.conditions.length) {
    parts.push(
      `Conditions: ${normalized.conditions.map((item) => item.name).join(", ")}`
    );
  }
  if (normalized.surgeries.length) {
    parts.push(
      `Surgeries: ${normalized.surgeries.map((item) => item.name).join(", ")}`
    );
  }
  if (normalized.allergies.length) {
    parts.push(
      `Allergies: ${normalized.allergies.map((item) => item.name).join(", ")}`
    );
  }
  return parts.length ? parts.join(" · ") : "No medical history recorded yet.";
}
