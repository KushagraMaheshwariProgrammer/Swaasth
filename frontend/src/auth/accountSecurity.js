import {
  EmailAuthProvider,
  GoogleAuthProvider,
  TotpMultiFactorGenerator,
  multiFactor,
  reauthenticateWithCredential,
  reauthenticateWithPopup,
  updatePassword,
  verifyBeforeUpdateEmail,
} from "firebase/auth";
import { auth } from "../firebase";
import { getAccountActionCodeSettings } from "./emailVerification";

const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: "login" });

export function usesPasswordProvider(user) {
  return user?.providerData?.some((provider) => provider.providerId === "password") ?? false;
}

export function getTotpFactors(user) {
  if (!user) {
    return [];
  }
  return multiFactor(user).enrolledFactors.filter(
    (factor) => factor.factorId === TotpMultiFactorGenerator.FACTOR_ID
  );
}

export function hasTotpMfa(user) {
  return getTotpFactors(user).length > 0;
}

export function getAccountErrorMessage(error) {
  const code = error?.code || "";
  if (code === "auth/wrong-password" || code === "auth/invalid-credential") {
    return "Current password is incorrect.";
  }
  if (code === "auth/weak-password") {
    return "New password must be at least 6 characters.";
  }
  if (code === "auth/email-already-in-use") {
    return "That email is already linked to another account.";
  }
  if (code === "auth/invalid-email") {
    return "Please enter a valid email address.";
  }
  if (code === "auth/requires-recent-login") {
    return "For security, confirm your identity and try again.";
  }
  if (code === "auth/too-many-requests") {
    return "Too many attempts. Please wait a few minutes and try again.";
  }
  if (code === "auth/invalid-verification-code") {
    return "Invalid authentication code. Use the latest code from your app.";
  }
  if (code === "auth/unverified-email") {
    return "Verify your current email before changing it.";
  }
  return error?.message || "Unable to complete this action. Please try again.";
}

export async function reauthenticateCurrentUser(password) {
  const user = auth.currentUser;
  if (!user) {
    throw new Error("You must be signed in.");
  }
  if (usesPasswordProvider(user)) {
    if (!password) {
      throw new Error("Enter your current password to continue.");
    }
    const credential = EmailAuthProvider.credential(user.email, password);
    await reauthenticateWithCredential(user, credential);
    return;
  }
  await reauthenticateWithPopup(user, googleProvider);
}

export async function changeUserPassword(currentPassword, newPassword) {
  await reauthenticateCurrentUser(currentPassword);
  await updatePassword(auth.currentUser, newPassword);
}

export async function changeUserEmail(currentPassword, newEmail) {
  await reauthenticateCurrentUser(currentPassword);
  await verifyBeforeUpdateEmail(
    auth.currentUser,
    newEmail.trim(),
    getAccountActionCodeSettings()
  );
}

export async function generateTotpEnrollment() {
  const user = auth.currentUser;
  const session = await multiFactor(user).getSession();
  const totpSecret = await TotpMultiFactorGenerator.generateSecret(session);
  return {
    totpSecret,
    qrCodeUrl: totpSecret.generateQrCodeUrl(user.email, "BillCheck"),
    secretKey: totpSecret.secretKey,
  };
}

export async function enrollTotpMfa(totpSecret, verificationCode, displayName = "Authenticator app") {
  const assertion = TotpMultiFactorGenerator.assertionForEnrollment(
    totpSecret,
    verificationCode.trim()
  );
  await multiFactor(auth.currentUser).enroll(assertion, displayName);
}

export async function unenrollTotpMfa(factorUid, currentPassword) {
  await reauthenticateCurrentUser(currentPassword);
  const factor = multiFactor(auth.currentUser).enrolledFactors.find(
    (entry) => entry.uid === factorUid
  );
  if (!factor) {
    throw new Error("Authenticator not found.");
  }
  await multiFactor(auth.currentUser).unenroll(factor);
}
