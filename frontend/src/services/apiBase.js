import { Capacitor } from "@capacitor/core";

const STORAGE_KEY = "swaasth_api_base";
const BACKEND_PORT = 8000;

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

function resolveNativeApiBase() {
  const stored = storedApiBase();
  if (stored) {
    return stored;
  }

  if (isAndroidEmulator()) {
    return platformFallbackApiBase();
  }

  const env = envApiBase();
  if (env) {
    return env;
  }

  return platformFallbackApiBase();
}

/** Backend root URL. Empty string on web dev uses the Vite proxy. */
export function getApiBase() {
  if (Capacitor.isNativePlatform()) {
    return resolveNativeApiBase();
  }
  return envApiBase() || storedApiBase() || "";
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
  return normalized;
}

export function backendConnectionHint() {
  const base = getApiBase();
  if (!Capacitor.isNativePlatform()) {
    return "Start the backend on port 8000 and refresh.";
  }
  if (isAndroidEmulator()) {
    return (
      `Using emulator host ${base}. ` +
      "Start the backend: cd backend && ./run_dev.sh (listens on 0.0.0.0:8000)."
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
      `Could not reach ${base}. ` +
      "Ensure ./run_dev.sh is running on your Mac (0.0.0.0:8000) and the phone is on the same Wi‑Fi."
    );
  }
  return (
    `Could not reach ${base || "the backend"}. ` +
    "Ensure ./run_dev.sh is running on your Mac (0.0.0.0:8000)."
  );
}
