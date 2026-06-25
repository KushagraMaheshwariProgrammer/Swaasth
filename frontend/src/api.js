export async function apiFetch(url, options = {}) {
  const { getIdToken, auth = false, headers: customHeaders, ...rest } = options;
  const headers = { ...customHeaders };

  if (auth) {
    if (!getIdToken) {
      throw new Error("Authentication is required for this request.");
    }
    const token = await getIdToken();
    if (!token) {
      throw new Error("You must be signed in to continue.");
    }
    headers.Authorization = `Bearer ${token}`;
  }

  return fetch(url, { ...rest, headers });
}
