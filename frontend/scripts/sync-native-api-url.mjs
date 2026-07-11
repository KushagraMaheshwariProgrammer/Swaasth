#!/usr/bin/env node
/**
 * Writes VITE_API_BASE to frontend/.env using this Mac's LAN IP so Capacitor
 * builds on a physical phone can reach the local backend.
 */
import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const envPath = path.join(frontendRoot, ".env");
const productionEnvPath = path.join(frontendRoot, ".env.production");

function readEnvValue(content, key) {
  const pattern = new RegExp(`^\\s*${key}\\s*=\\s*(.*?)\\s*$`, "m");
  const match = content.match(pattern);
  return match?.[1]?.replace(/^(['"])(.*)\\1$/, "$2").trim() || "";
}

function detectLanIp() {
  if (process.env.SWAASTH_BUILD_TARGET === "emulator") {
    return null;
  }
  for (const iface of ["en0", "en1", "wlan0", "eth0"]) {
    try {
      if (process.platform === "darwin") {
        const ip = execSync(`ipconfig getifaddr ${iface}`, {
          encoding: "utf8",
        }).trim();
        if (ip) {
          return ip;
        }
      } else {
        const ip = execSync(`hostname -I`, { encoding: "utf8" })
          .trim()
          .split(/\s+/)[0];
        if (ip) {
          return ip;
        }
      }
    } catch {
      // try next interface
    }
  }
  return null;
}

function upsertEnvLine(content, key, value) {
  const line = `${key}=${value}`;
  const pattern = new RegExp(`^${key}=.*$`, "m");
  if (pattern.test(content)) {
    return content.replace(pattern, line);
  }
  const trimmed = content.trimEnd();
  return trimmed ? `${trimmed}\n${line}\n` : `${line}\n`;
}

let content = "";
if (fs.existsSync(envPath)) {
  content = fs.readFileSync(envPath, "utf8");
}

const productionContent = fs.existsSync(productionEnvPath)
  ? fs.readFileSync(productionEnvPath, "utf8")
  : "";
// The production env file is the source of truth for release builds. A stale
// exported shell variable must not silently replace it with a LAN address.
const configuredApiBase =
  readEnvValue(productionContent, "VITE_API_BASE") ||
  readEnvValue(content, "VITE_API_BASE") ||
  process.env.VITE_API_BASE?.trim();
const ip = configuredApiBase ? null : detectLanIp();
if (!ip) {
  if (process.env.SWAASTH_BUILD_TARGET === "emulator") {
    const apiBase = "http://10.0.2.2:8000";
    const next = upsertEnvLine(content, "VITE_API_BASE", apiBase);
    fs.writeFileSync(envPath, next, "utf8");
    console.log(`sync-native-api-url: set VITE_API_BASE=${apiBase} for Android emulator`);
    process.exit(0);
  }
  if (configuredApiBase) {
    console.log(`sync-native-api-url: keeping configured VITE_API_BASE=${configuredApiBase}`);
  } else {
    console.log("sync-native-api-url: LAN IP not found; skipping.");
  }
  process.exit(0);
}

const apiBase = `http://${ip}:8000`;
const next = upsertEnvLine(content, "VITE_API_BASE", apiBase);
fs.writeFileSync(envPath, next, "utf8");
console.log(`sync-native-api-url: set VITE_API_BASE=${apiBase} in frontend/.env`);
