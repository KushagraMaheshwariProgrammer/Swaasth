import { Capacitor } from "@capacitor/core";
import { FirebaseAuthentication } from "@capacitor-firebase/authentication";
import {
  EmailAuthProvider,
  GoogleAuthProvider,
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
  if (Capacitor.isNativePlatform()) {
    const result = await FirebaseAuthentication.signInWithGoogle({
      skipNativeAuth: true,
    });
    const idToken = result.credential?.idToken;
    if (!idToken) {
      throw new Error("Google re-authentication did not return an ID token.");
    }
    const credential = GoogleAuthProvider.credential(idToken);
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
