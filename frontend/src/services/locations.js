import bundle from "../data/locations.bundle.json";

const DEFAULT_TIER = {
  tier_id: "tier_3",
  tier_label: "Tier III (Z City)",
  tier_source: "default_tier_3",
};

/**
 * Canonical list of Indian States & Union Territories.
 * Used as a baseline so the patient form always offers every State/UT (the
 * bundled bill-checker directory predates the Telangana split and omits it).
 */
const CANONICAL_INDIA_STATES_UTS = [
  "Andhra Pradesh",
  "Arunachal Pradesh",
  "Assam",
  "Bihar",
  "Chhattisgarh",
  "Goa",
  "Gujarat",
  "Haryana",
  "Himachal Pradesh",
  "Jharkhand",
  "Karnataka",
  "Kerala",
  "Madhya Pradesh",
  "Maharashtra",
  "Manipur",
  "Meghalaya",
  "Mizoram",
  "Nagaland",
  "Odisha",
  "Punjab",
  "Rajasthan",
  "Sikkim",
  "Tamil Nadu",
  "Telangana",
  "Tripura",
  "Uttar Pradesh",
  "Uttarakhand",
  "West Bengal",
  "Andaman and Nicobar Islands",
  "Chandigarh",
  "Dadra and Nagar Haveli and Daman and Diu",
  "Delhi",
  "Jammu and Kashmir",
  "Ladakh",
  "Lakshadweep",
  "Puducherry",
];

/** State/UT names from the bundled official directory (same data as the backend). */
export function getStates() {
  return Array.isArray(bundle.states) ? bundle.states : [];
}

/**
 * Complete, sorted list of State/UT names for selection forms (e.g. the patient
 * form). Merges the bundled directory with the canonical list so no State/UT is
 * missing regardless of the bundle's vintage.
 */
export function getStateOptions() {
  const names = new Set([...getStates(), ...CANONICAL_INDIA_STATES_UTS]);
  return [...names].sort((a, b) => a.localeCompare(b));
}

/**
 * Safe comparison for the Telangana State across name, code and casing
 * variations (e.g. "Telangana", " telangana ", "TG", "TS", "36").
 */
export function isTelanganaState(value) {
  if (value == null) {
    return false;
  }
  const normalized = String(value).trim().toLowerCase();
  if (!normalized) {
    return false;
  }
  return ["telangana", "tg", "ts", "36"].includes(normalized);
}

/** Normalize patient / form state values to a bundled directory state name. */
export function resolveCanonicalStateUtName(value) {
  const trimmed = String(value || "").trim();
  if (!trimmed) {
    return "";
  }

  if (bundle.citiesByState?.[trimmed]) {
    return trimmed;
  }

  const lower = trimmed.toLowerCase();
  if (isTelanganaState(trimmed)) {
    return "Telangana";
  }

  const fromOptions = getStateOptions().find(
    (name) => name.toLowerCase() === lower
  );
  if (fromOptions) {
    return fromOptions;
  }

  const fromBundle = getStates().find((name) => name.toLowerCase() === lower);
  return fromBundle || trimmed;
}

/** City names for a state/UT from the bundled directory. */
export function getCities(stateUtName) {
  if (!stateUtName) {
    return [];
  }
  const canonical = resolveCanonicalStateUtName(stateUtName);
  const cities = bundle.citiesByState?.[canonical];
  return Array.isArray(cities) ? cities : [];
}

/** City tier for a state + city using bundled classification data. */
export function resolveCityTier(stateUtName, cityName) {
  if (!stateUtName || !cityName) {
    return null;
  }

  const canonical = resolveCanonicalStateUtName(stateUtName);
  const tier = bundle.tierByStateCity?.[canonical]?.[cityName];
  return {
    state_ut_name: canonical,
    city_name: cityName,
    ...(tier || DEFAULT_TIER),
  };
}
