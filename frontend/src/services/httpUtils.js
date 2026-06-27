import { backendConnectionHint, ensureApiBase, getApiBase } from "./apiBase";
import { Capacitor } from "@capacitor/core";

export function backendUnreachableMessage() {
  if (Capacitor.isNativePlatform()) {
    return `Could not reach the backend at ${getApiBase() || "(not configured)"}. ${backendConnectionHint()}`;
  }
  return `Could not reach the backend. ${backendConnectionHint()}`;
}

async function fetchWithNativeRetry(url, options) {
  try {
    return await fetch(url, options);
  } catch (error) {
    if (!Capacitor.isNativePlatform()) {
      throw error;
    }
    const previousBase = getApiBase();
    const nextBase = await ensureApiBase({ force: true });
    if (!nextBase || nextBase === previousBase) {
      throw error;
    }
    const rewrittenUrl = url.replace(previousBase, nextBase);
    return fetch(rewrittenUrl, options);
  }
}

export async function fetchBackend(url, options) {
  if (Capacitor.isNativePlatform()) {
    await ensureApiBase();
  }
  try {
    return await fetchWithNativeRetry(url, options);
  } catch {
    throw new Error(backendUnreachableMessage());
  }
}

/** Parse a fetch Response safely; avoids \"Unexpected end of JSON input\". */
export async function parseJsonResponse(response) {
  let text = "";
  try {
    text = await response.text();
  } catch {
    throw new Error(backendUnreachableMessage());
  }

  let payload = null;
  if (text.trim()) {
    try {
      payload = JSON.parse(text);
    } catch {
      if (!response.ok) {
        throw new Error(
          response.status >= 502 && response.status <= 504
            ? backendUnreachableMessage()
            : `Server returned an invalid response (HTTP ${response.status}).`
        );
      }
      throw new Error("Server returned an invalid JSON response.");
    }
  }

  if (!response.ok) {
    const detail = payload?.detail;
    const message = Array.isArray(detail)
      ? detail.map((entry) => entry.msg).join(", ")
      : detail;
    if (message) {
      throw new Error(message);
    }
    if (response.status >= 502 && response.status <= 504) {
      throw new Error(backendUnreachableMessage());
    }
    if (!text.trim()) {
      throw new Error(
        `Server returned HTTP ${response.status} with an empty body. ${backendUnreachableMessage()}`
      );
    }
    throw new Error(`Request failed (HTTP ${response.status}).`);
  }

  return payload ?? {};
}

export async function fetchJson(url, options) {
  let response;
  try {
    if (Capacitor.isNativePlatform()) {
      await ensureApiBase();
    }
    response = await fetchWithNativeRetry(url, options);
  } catch {
    throw new Error(backendUnreachableMessage());
  }
  return parseJsonResponse(response);
}
