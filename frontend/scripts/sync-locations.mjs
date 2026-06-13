import { execSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const backendRoot = join(root, "..", "backend");
const pythonCandidates = [
  join(backendRoot, ".venv", "bin", "python"),
  join(backendRoot, "venv", "bin", "python"),
];

const python = pythonCandidates.find((candidate) => existsSync(candidate)) || "python3";
const script = join(backendRoot, "scripts", "export_locations_bundle.py");

execSync(`"${python}" "${script}"`, {
  cwd: backendRoot,
  stdio: "inherit",
});
