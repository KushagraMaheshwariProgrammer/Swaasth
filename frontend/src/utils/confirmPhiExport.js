const DEFAULT_MESSAGE =
  "This will share medical information outside the app. Continue?";

/**
 * Ask the user to confirm before PHI leaves the app via share/clipboard.
 * Returns false if cancelled.
 */
export function confirmPhiExport(message = DEFAULT_MESSAGE) {
  if (typeof window === "undefined" || typeof window.confirm !== "function") {
    return true;
  }
  return window.confirm(message);
}
