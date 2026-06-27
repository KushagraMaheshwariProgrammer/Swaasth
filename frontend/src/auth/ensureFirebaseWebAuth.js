import { auth } from "../firebase";

/** Ensure the Firebase JS auth session is ready before Firestore reads. */
export async function ensureFirebaseWebAuth() {
  await auth.authStateReady();

  if (!auth.currentUser) {
    return null;
  }

  try {
    await auth.currentUser.getIdToken();
  } catch (error) {
    console.warn("Could not refresh Firebase auth token:", error);
  }

  return auth.currentUser;
}
