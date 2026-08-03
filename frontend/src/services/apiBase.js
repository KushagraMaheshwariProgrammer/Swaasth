import { Capacitor } from "@capacitor/core";

const STORAGE_KEY = "swaasth_api_base";
const BACKEND_PORT = 8000;
const PROBE_TIMEOUT_MS = 15000;

let resolvedApiBase = "";
let probePromise = null;

function trimBase(url) {
  return String(url || "").trim().replace(/\/$/, "");
}

function envApiBase() {
  return trimBase(import.meta.env.VITE_API_BASE);
}

function storedApiBase() {
  if (typeof localStorage === "undefined") {
    return "";
  }
  return trimBase(localStorage.getItem(STORAGE_KEY));
}

function isPrivateLanHost(hostname) {
  if (!hostname) {
    return false;
  }
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return true;
  }
  if (/^192\.168\.\d{1,3}\.\d{1,3}$/.test(hostname)) {
    return true;
  }
  if (/^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(hostname) && hostname !== "10.0.2.2") {
    return true;
  }
  return false;
}

/** Android emulators cannot reach the host Mac via LAN IPs — they need 10.0.2.2. */
export function isAndroidEmulator() {
  if (Capacitor.getPlatform() !== "android") {
    return false;
  }
  const ua = navigator.userAgent || "";
  return /sdk_gphone|sdk_google_phone|Android SDK built for x86|emulator|Genymotion|google_sdk/i.test(
    ua
  );
}

function platformFallbackApiBase() {
  if (!Capacitor.isNativePlatform()) {
    return "";
  }
  if (Capacitor.getPlatform() === "android") {
    return `http://10.0.2.2:${BACKEND_PORT}`;
  }
  return `http://127.0.0.1:${BACKEND_PORT}`;
}

function uniqueBases(bases) {
  const seen = new Set();
  const ordered = [];
  for (const base of bases) {
    const normalized = trimBase(base);
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    ordered.push(normalized);
  }
  return ordered;
}

/** Ordered candidates for native backend discovery. */
export function getApiBaseCandidates() {
  if (!Capacitor.isNativePlatform()) {
    const webBase = envApiBase() || storedApiBase();
    return webBase ? [webBase] : [];
  }

  const candidates = [];

  if (isAndroidEmulator()) {
    candidates.push(platformFallbackApiBase());
  }

  const env = envApiBase();
  if (env) {
    candidates.push(env);
  }

  const stored = storedApiBase();
  if (stored) {
    candidates.push(stored);
  }

  if (!isAndroidEmulator()) {
    candidates.push(platformFallbackApiBase());
  }

  return uniqueBases(candidates);
}

function resolveNativeApiBaseSync() {
  const candidates = getApiBaseCandidates();
  if (candidates.length) {
    return candidates[0];
  }
  return platformFallbackApiBase();
}

async function probeBackend(base) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);
  try {
    const response = await fetch(`${base}/ready`, {
      method: "GET",
      signal: controller.signal,
    });
    if (response.ok) {
      return true;
    }
    // Warmup in progress — API is reachable even while indexes load.
    if (response.status === 503) {
      return true;
    }
    const health = await fetch(`${base}/health`, {
      method: "GET",
      signal: controller.signal,
    });
    return health.ok;
  } catch {
    try {
      const health = await fetch(`${base}/health`, {
        method: "GET",
        signal: controller.signal,
      });
      return health.ok;
    } catch {
      return false;
    }
  } finally {
    window.clearTimeout(timer);
  }
}

/**
 * Find a reachable backend URL on native (LAN IP changes, emulator vs phone, stale cache).
 * Caches the working base in memory and localStorage.
 */
export async function ensureApiBase({ force = false } = {}) {
  if (!Capacitor.isNativePlatform()) {
    const env = envApiBase();
    const stored = storedApiBase();
    const candidate = env || (import.meta.env.DEV ? "" : stored);

    if (!candidate) {
      if (import.meta.env.DEV && stored) {
        clearStoredApiBase();
      }
      resolvedApiBase = "";
      return "";
    }

    if (!force && resolvedApiBase === candidate) {
      return candidate;
    }

    if (await probeBackend(candidate)) {
      resolvedApiBase = candidate;
      return candidate;
    }

    if (import.meta.env.DEV) {
      clearStoredApiBase();
      resolvedApiBase = "";
      return "";
    }

    resolvedApiBase = candidate;
    return candidate;
  }

  if (resolvedApiBase && !force) {
    return resolvedApiBase;
  }

  if (probePromise && !force) {
    return probePromise;
  }

  probePromise = (async () => {
    const candidates = getApiBaseCandidates();
    for (const base of candidates) {
      if (await probeBackend(base)) {
        resolvedApiBase = base;
        setApiBase(base);
        return base;
      }
    }

    const fallback = resolveNativeApiBaseSync();
    resolvedApiBase = fallback;
    return fallback;
  })();

  try {
    return await probePromise;
  } finally {
    probePromise = null;
  }
}

/** Backend root URL. Empty string on web dev uses the Vite proxy. */
export function getApiBase() {
  if (Capacitor.isNativePlatform()) {
    return resolvedApiBase || resolveNativeApiBaseSync();
  }

  const env = envApiBase();
  if (env) {
    return env;
  }

  // Web dev: ignore stale localStorage from native/LAN testing; use Vite proxy.
  if (import.meta.env.DEV) {
    return resolvedApiBase || "";
  }

  return storedApiBase() || "";
}

export function setApiBase(url) {
  const normalized = trimBase(url);
  if (typeof localStorage !== "undefined") {
    if (normalized) {
      localStorage.setItem(STORAGE_KEY, normalized);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }
  resolvedApiBase = normalized;
  return normalized;
}

export function clearStoredApiBase() {
  if (typeof localStorage !== "undefined") {
    localStorage.removeItem(STORAGE_KEY);
  }
  resolvedApiBase = "";
}

export function backendConnectionHint() {
  const base = getApiBase();
  if (!Capacitor.isNativePlatform()) {
    if (import.meta.env.DEV) {
      return (
        "Start the backend: cd backend && ./run_dev.sh (port 8000), then hard-refresh " +
        "this page at http://localhost:5173."
      );
    }
    return "Start the backend on port 8000 and refresh.";
  }
  if (isAndroidEmulator()) {
    return (
      `Tried ${getApiBaseCandidates().join(", ") || base}. ` +
      "Start the backend: cd backend && ./run_dev.sh (listens on 0.0.0.0:8000), then reopen the app."
    );
  }
  if (base.includes("10.0.2.2")) {
    return (
      "Physical phones cannot use 10.0.2.2. From the frontend folder run: " +
      "npm run native:api-url && npm run build, then reinstall the app. " +
      "Phone and Mac must be on the same Wi‑Fi."
    );
  }
  let host = "";
  try {
    host = new URL(base).hostname;
  } catch {
    host = "";
  }
  if (isPrivateLanHost(host)) {
    return (
      "Ensure ./run_dev.sh is running on your Mac (0.0.0.0:8000) and the phone is on the same Wi‑Fi. " +
      "Then run: cd frontend && npm run native:api-url && npm run build"
    );
  }
  if (base.startsWith("https://")) {
    return (
      "Check that your phone has internet access and try again. " +
      "If other apps work, try switching between Wi‑Fi and mobile data — " +
      "some Wi‑Fi routers fail to resolve this server's address."
    );
  }
  return "Ensure ./run_dev.sh is running on your Mac (0.0.0.0:8000).";
}
