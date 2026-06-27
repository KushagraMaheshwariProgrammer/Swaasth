import { getApiBase } from "./apiBase";
import { backendUnreachableMessage } from "./httpUtils";

function pmjayBase() {
  return `${getApiBase()}/api/schemes/pmjay`;
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${pmjayBase()}${path}`, options);
  } catch {
    throw new Error(backendUnreachableMessage());
  }
  if (!response.ok) {
    throw new Error("PM-JAY hospital data is currently unavailable.");
  }
  return response.json();
}

export function searchPmjayHospitals({
  query = "",
  state = "",
  district = "",
  city = "",
  hospitalType = "",
  limit = 20,
  offset = 0,
} = {}) {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (state) params.set("state", state);
  if (district) params.set("district", district);
  if (city) params.set("city", city);
  if (hospitalType) params.set("hospital_type", hospitalType);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  return request(`/hospitals/search?${params.toString()}`);
}

export function fetchPmjayFilters({ state = "", district = "" } = {}) {
  const params = new URLSearchParams();
  if (state) params.set("state", state);
  if (district) params.set("district", district);
  return request(`/filters?${params.toString()}`);
}

export function verifyPmjayHospital({
  hospitalName,
  state = "",
  district = "",
  city = "",
  pmjayHasAyushmanCard = null,
}) {
  return request("/verify-hospital", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      hospital_name: hospitalName,
      state: state || null,
      district: district || null,
      city: city || null,
      pmjay_has_ayushman_card: pmjayHasAyushmanCard,
    }),
  });
}
