import { existsSync, readFileSync } from "node:fs";

if (!existsSync(".env.production")) {
  console.error(
    "\nMissing frontend/.env.production\n" +
      "Copy .env.production.example to .env.production and set VITE_API_BASE " +
      "to your deployed backend URL (HTTPS).\n"
  );
  process.exit(1);
}

const env = readFileSync(".env.production", "utf8");
const match = env.match(/^VITE_API_BASE=(.+)$/m);
const value = match?.[1]?.trim().replace(/^["']|["']$/g, "");

if (!value || value.includes("your-backend.onrender.com")) {
  console.error(
    "\nSet VITE_API_BASE in frontend/.env.production to your live backend URL.\n" +
      "Deploy the backend first (see render.yaml in repo root), then paste the HTTPS URL.\n"
  );
  process.exit(1);
}

if (!/^https:\/\/.+/i.test(value)) {
  console.error(
    "\nRelease APK builds require HTTPS for VITE_API_BASE (e.g. https://swaasth-api.onrender.com).\n"
  );
  process.exit(1);
}

console.log(`Release build will use API: ${value.replace(/\/$/, "")}`);
