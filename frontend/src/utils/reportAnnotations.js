export function buildFlagKey(flag, index = 0) {
  const type = String(flag?.type || "flag").trim();
  const item = String(flag?.item || `item-${index}`).trim();
  return `${type}::${item}`;
}

export function emptyClinicianAnnotations() {
  return {
    general_note: "",
    flag_notes: {},
    updated_at: null,
  };
}

export function normalizeClinicianAnnotations(value) {
  if (!value || typeof value !== "object") {
    return emptyClinicianAnnotations();
  }
  const flagNotes = {};
  for (const [key, entry] of Object.entries(value.flag_notes || {})) {
    if (!entry || typeof entry !== "object") {
      continue;
    }
    const text = String(entry.text || "").trim();
    if (!text) {
      continue;
    }
    flagNotes[key] = {
      text,
      updated_at: entry.updated_at || null,
    };
  }
  return {
    general_note: String(value.general_note || "").trim(),
    flag_notes: flagNotes,
    updated_at: value.updated_at || null,
  };
}

export function getFlagAnnotation(annotations, flag, index = 0) {
  const normalized = normalizeClinicianAnnotations(annotations);
  return normalized.flag_notes[buildFlagKey(flag, index)]?.text || "";
}

export function setFlagAnnotation(annotations, flag, index, text) {
  const normalized = normalizeClinicianAnnotations(annotations);
  const key = buildFlagKey(flag, index);
  const trimmed = String(text || "").trim();
  const nextNotes = { ...normalized.flag_notes };
  if (trimmed) {
    nextNotes[key] = {
      text: trimmed,
      updated_at: new Date().toISOString(),
    };
  } else {
    delete nextNotes[key];
  }
  return {
    ...normalized,
    flag_notes: nextNotes,
    updated_at: new Date().toISOString(),
  };
}

export function setGeneralAnnotationNote(annotations, text) {
  const normalized = normalizeClinicianAnnotations(annotations);
  return {
    ...normalized,
    general_note: String(text || "").trim(),
    updated_at: new Date().toISOString(),
  };
}

export function collectAllFlags(report) {
  const treatmentFlags = report?.treatment_audit_flags?.flags || [];
  const billingFlags = report?.audit_flags?.flags || [];
  return [...billingFlags, ...treatmentFlags];
}
