import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  createUserWithEmailAndPassword,
  getRedirectResult,
  GoogleAuthProvider,
  onAuthStateChanged,
  sendEmailVerification,
  signInWithEmailAndPassword,
  signInWithPopup,
  signInWithRedirect,
  signOut,
} from "firebase/auth";
import { auth } from "../firebase";
import { syncPendingBills } from "../services/bills";

const AuthContext = createContext(null);

const googleProvider = new GoogleAuthProvider();
googleProvider.addScope("email");
googleProvider.addScope("profile");
googleProvider.setCustomParameters({ prompt: "select_account" });

export function needsEmailVerification(user) {
  if (!user) {
    return false;
  }
  const usesPasswordProvider = user.providerData.some(
    (provider) => provider.providerId === "password"
  );
  return usesPasswordProvider && !user.emailVerified;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [redirectHandled, setRedirectHandled] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const bootstrapAuth = async () => {
      try {
        await getRedirectResult(auth);
      } catch (error) {
        console.error("Google redirect sign-in failed:", error);
      } finally {
        if (!cancelled) {
          setRedirectHandled(true);
        }
      }
    };

    bootstrapAuth();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!redirectHandled) {
      return undefined;
    }

    const unsubscribe = onAuthStateChanged(auth, (nextUser) => {
      setUser(nextUser);
      setLoading(false);
      if (nextUser && !needsEmailVerification(nextUser)) {
        syncPendingBills(nextUser.uid).catch((error) => {
          console.error("Background bill sync failed:", error);
        });
      }
    });
    return unsubscribe;
  }, [redirectHandled]);

  const signUpWithEmail = useCallback(async (email, password) => {
    const credential = await createUserWithEmailAndPassword(auth, email, password);
    await sendEmailVerification(credential.user);
    return credential;
  }, []);

  const signInWithEmail = useCallback(async (email, password) => {
    return signInWithEmailAndPassword(auth, email, password);
  }, []);

  const signInWithGoogle = useCallback(async () => {
    try {
      return await signInWithPopup(auth, googleProvider);
    } catch (error) {
      const popupIssues = new Set([
        "auth/popup-blocked",
        "auth/popup-closed-by-user",
        "auth/cancelled-popup-request",
        "auth/operation-not-supported-in-this-environment",
      ]);
      if (popupIssues.has(error?.code)) {
        await signInWithRedirect(auth, googleProvider);
        return null;
      }
      throw error;
    }
  }, []);

  const resendVerificationEmail = useCallback(async () => {
    if (!auth.currentUser) {
      throw new Error("You must be signed in to resend the verification email.");
    }
    await sendEmailVerification(auth.currentUser);
  }, []);

  const reloadUser = useCallback(async () => {
    if (!auth.currentUser) {
      return null;
    }
    await auth.currentUser.reload();
    const refreshed = auth.currentUser;
    setUser(refreshed);
    return refreshed;
  }, []);

  const logOut = useCallback(async () => {
    return signOut(auth);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading: loading || !redirectHandled,
      needsEmailVerification: needsEmailVerification(user),
      signUpWithEmail,
      signInWithEmail,
      signInWithGoogle,
      resendVerificationEmail,
      reloadUser,
      logOut,
    }),
    [
      user,
      loading,
      redirectHandled,
      signUpWithEmail,
      signInWithEmail,
      signInWithGoogle,
      resendVerificationEmail,
      reloadUser,
      logOut,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
