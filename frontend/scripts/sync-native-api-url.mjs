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

function detectLanIp() {
  if (process.env.SWAASTH_BUILD_TARGET === "emulator") {
    return null;
  }
  if (process.env.VITE_API_BASE?.trim()) {
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

const ip = detectLanIp();
if (!ip) {
  if (process.env.SWAASTH_BUILD_TARGET === "emulator") {
    const apiBase = "http://10.0.2.2:8000";
    let content = "";
    if (fs.existsSync(envPath)) {
      content = fs.readFileSync(envPath, "utf8");
    }
    const next = upsertEnvLine(content, "VITE_API_BASE", apiBase);
    fs.writeFileSync(envPath, next, "utf8");
    console.log(`sync-native-api-url: set VITE_API_BASE=${apiBase} for Android emulator`);
    process.exit(0);
  }
  console.log("sync-native-api-url: VITE_API_BASE already set or LAN IP not found; skipping.");
  process.exit(0);
}

const apiBase = `http://${ip}:8000`;
let content = "";
if (fs.existsSync(envPath)) {
  content = fs.readFileSync(envPath, "utf8");
}

const next = upsertEnvLine(content, "VITE_API_BASE", apiBase);
fs.writeFileSync(envPath, next, "utf8");
console.log(`sync-native-api-url: set VITE_API_BASE=${apiBase} in frontend/.env`);
