import { getApiBase } from "./apiBase";
import { backendUnreachableMessage } from "./httpUtils";

function cghsBase() {
  return `${getApiBase()}/api/schemes/cghs`;
}

let cachedCoveredCities = null;
let cachedCoveredCitiesPromise = null;

export async function fetchCghsCoveredCities({ forceRefresh = false } = {}) {
  if (!forceRefresh && cachedCoveredCities) {
    return cachedCoveredCities;
  }
  if (!forceRefresh && cachedCoveredCitiesPromise) {
    return cachedCoveredCitiesPromise;
  }

  cachedCoveredCitiesPromise = (async () => {
    let response;
    try {
      response = await fetch(`${cghsBase()}/covered-cities`);
    } catch (error) {
      throw new Error(backendUnreachableMessage());
    }

    if (!response.ok) {
      throw new Error("CGHS covered cities are currently unavailable.");
    }

    const payload = await response.json();
    cachedCoveredCities = payload;
    return payload;
  })();

  try {
    return await cachedCoveredCitiesPromise;
  } finally {
    cachedCoveredCitiesPromise = null;
  }
}

export function filterCghsCoveredCities(cities = [], query = "") {
  const normalizedQuery = String(query || "").trim().toLowerCase();
  if (!normalizedQuery) {
    return cities;
  }

  return cities.filter((city) => {
    const displayName = String(city.city_display_name || "").toLowerCase();
    if (displayName.includes(normalizedQuery)) {
      return true;
    }
    return (city.aliases || []).some((alias) =>
      String(alias || "").toLowerCase().includes(normalizedQuery)
    );
  });
}
