import { backendConnectionHint, clearStoredApiBase, ensureApiBase, getApiBase } from "./apiBase";
import { Capacitor } from "@capacitor/core";

const DEFAULT_FETCH_TIMEOUT_MS = 120000;

const GENERIC_HTTP_PHRASES = new Set([
  "bad request",
  "unauthorized",
  "forbidden",
  "not found",
  "method not allowed",
  "not acceptable",
  "request timeout",
  "conflict",
  "gone",
  "length required",
  "precondition failed",
  "payload too large",
  "uri too long",
  "unsupported media type",
  "unprocessable entity",
  "too many requests",
  "internal server error",
  "not implemented",
  "bad gateway",
  "service unavailable",
  "gateway timeout",
]);

function isGenericHttpPhrase(message) {
  return GENERIC_HTTP_PHRASES.has(String(message || "").trim().toLowerCase());
}

function looksLikeHtml(text) {
  const trimmed = String(text || "").trim();
  return /^<!doctype html/i.test(trimmed) || /^<html[\s>]/i.test(trimmed);
}

function formatValidationLocation(loc) {
  if (!Array.isArray(loc) || !loc.length) {
    return "";
  }
  const parts = loc.filter((part) => part !== "body" && part !== "query");
  if (!parts.length) {
    return "";
  }
  return parts.map((part) => String(part)).join(" → ");
}

function formatValidationEntry(entry) {
  if (!entry || typeof entry !== "object") {
    return "";
  }
  const msg = String(entry.msg || entry.message || "").trim();
  if (!msg) {
    return "";
  }
  const field = formatValidationLocation(entry.loc);
  if (!field) {
    return msg;
  }
  if (/^field required$/i.test(msg) || /^missing$/i.test(msg)) {
    return `Missing ${field}.`;
  }
  return `${field}: ${msg}`;
}

function pickFirstString(...values) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return "";
}

/** Extract a patient-friendly message from an API error payload or body text. */
export function extractApiErrorMessage(payload, text, response, fallback) {
  const status = response?.status ?? 0;
  const defaultFallback =
    fallback ||
    (status === 400
      ? "We could not process your request. Check the file or details and try again."
      : `Request failed (HTTP ${status || "unknown"}).`);

  let message = "";

  if (payload && typeof payload === "object") {
    const detail = payload.detail;
    if (typeof detail === "string") {
      message = detail.trim();
    } else if (Array.isArray(detail)) {
      message = detail
        .map((entry) => formatValidationEntry(entry))
        .filter(Boolean)
        .join(" ");
    } else if (detail && typeof detail === "object") {
      message = pickFirstString(detail.message, detail.error, detail.detail);
    }

    if (!message) {
      message = pickFirstString(payload.message, payload.error);
    }
    if (!message && payload.error && typeof payload.error === "object") {
      message = pickFirstString(payload.error.message, payload.error.detail);
    }
  } else if (typeof payload === "string") {
    message = payload.trim();
  }

  if (!message && text?.trim() && !looksLikeHtml(text)) {
    const trimmed = text.trim();
    if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) {
      message = trimmed;
    }
  }

  if (message && !isGenericHttpPhrase(message)) {
    return message;
  }

  return defaultFallback;
}

export function backendUnreachableMessage() {
  if (Capacitor.isNativePlatform()) {
    return `Could not reach the backend at ${getApiBase() || "(not configured)"}. ${backendConnectionHint()}`;
  }
  return `Could not reach the backend. ${backendConnectionHint()}`;
}

async function fetchWithTimeout(url, options, timeoutMs = DEFAULT_FETCH_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error(
        `Request timed out after ${Math.round(timeoutMs / 1000)}s. ${backendConnectionHint()}`
      );
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

async function fetchWithNativeRetry(url, options) {
  try {
    return await fetchWithTimeout(url, options);
  } catch (error) {
    if (!Capacitor.isNativePlatform()) {
      const base = getApiBase();
      if (import.meta.env.DEV && base) {
        clearStoredApiBase();
        const proxiedUrl = url.startsWith(base) ? url.slice(base.length) : url;
        return fetchWithTimeout(proxiedUrl, options);
      }
      throw error;
    }
    const previousBase = getApiBase();
    const nextBase = await ensureApiBase({ force: true });
    if (!nextBase || nextBase === previousBase) {
      throw error;
    }
    const rewrittenUrl = url.replace(previousBase, nextBase);
    return fetchWithTimeout(rewrittenUrl, options);
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
        if (response.status >= 502 && response.status <= 504) {
          throw new Error(backendUnreachableMessage());
        }
        throw new Error(extractApiErrorMessage(null, text, response));
      }
      throw new Error("Server returned an invalid JSON response.");
    }
  }

  if (!response.ok) {
    if (response.status >= 502 && response.status <= 504) {
      throw new Error(backendUnreachableMessage());
    }
    throw new Error(extractApiErrorMessage(payload, text, response));
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
