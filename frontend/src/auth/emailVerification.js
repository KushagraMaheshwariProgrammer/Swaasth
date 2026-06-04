export function getEmailVerificationActionCodeSettings() {
  return {
    url: `${window.location.origin}/verify-email`,
    handleCodeInApp: true,
  };
}

export function getAccountActionCodeSettings() {
  return {
    url: `${window.location.origin}/account`,
    handleCodeInApp: true,
  };
}

export function getEmailVerificationLinkParams() {
  const params = new URLSearchParams(window.location.search);
  const mode = params.get("mode");
  const oobCode = params.get("oobCode");
  if (mode === "verifyEmail" && oobCode) {
    return { oobCode };
  }
  return null;
}

export function clearEmailVerificationLinkParams() {
  const url = new URL(window.location.href);
  for (const key of ["mode", "oobCode", "apiKey", "lang", "continueUrl"]) {
    url.searchParams.delete(key);
  }
  const nextPath = `${url.pathname}${url.search}${url.hash}`;
  window.history.replaceState({}, document.title, nextPath || "/verify-email");
}

export function getVerificationErrorMessage(error) {
  const code = error?.code || "";
  if (code === "auth/too-many-requests") {
    return "Too many verification emails sent. Please wait a few minutes before trying again.";
  }
  if (code === "auth/expired-action-code") {
    return "This verification link has expired. Resend a new verification email.";
  }
  if (code === "auth/invalid-action-code") {
    return "This verification link is invalid or was already used. Resend a new verification email.";
  }
  if (code === "auth/invalid-continue-uri") {
    return "This site is not authorized for email verification links. Contact support.";
  }
  return error?.message || "Unable to send verification email. Please try again.";
}
