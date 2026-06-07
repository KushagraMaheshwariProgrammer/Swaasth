import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  applyActionCode,
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
import {
  changeUserEmail,
  changeUserPassword,
  usesPasswordProvider,
} from "../auth/accountSecurity";
import {
  clearEmailVerificationLinkParams,
  getEmailVerificationActionCodeSettings,
  getEmailVerificationLinkParams,
  getVerificationErrorMessage,
} from "../auth/emailVerification";
import { auth } from "../firebase";
import { syncPendingBills } from "../services/bills";
import { syncPendingPatients } from "../services/patients";

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

const idleEmailLinkVerification = { status: "idle", message: "" };

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [redirectHandled, setRedirectHandled] = useState(false);
  const [emailLinkVerification, setEmailLinkVerification] = useState(
    idleEmailLinkVerification
  );

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
        syncPendingPatients(nextUser.uid).catch((error) => {
          console.error("Background patient sync failed:", error);
        });
        syncPendingBills(nextUser.uid).catch((error) => {
          console.error("Background bill sync failed:", error);
        });
      }
    });
    return unsubscribe;
  }, [redirectHandled]);

  useEffect(() => {
    const linkParams = getEmailVerificationLinkParams();
    if (!linkParams) {
      return undefined;
    }

    let cancelled = false;
    setEmailLinkVerification({ status: "processing", message: "" });

    const completeVerificationLink = async () => {
      try {
        await applyActionCode(auth, linkParams.oobCode);
        clearEmailVerificationLinkParams();

        if (auth.currentUser) {
          await auth.currentUser.reload();
          if (!cancelled) {
            setUser(auth.currentUser);
          }
        }

        if (!cancelled) {
          setEmailLinkVerification({
            status: "success",
            message: "Your email has been verified.",
          });
        }
      } catch (error) {
        clearEmailVerificationLinkParams();
        if (!cancelled) {
          setEmailLinkVerification({
            status: "error",
            message: getVerificationErrorMessage(error),
          });
        }
      }
    };

    completeVerificationLink();
    return () => {
      cancelled = true;
    };
  }, []);

  const signUpWithEmail = useCallback(async (email, password) => {
    const credential = await createUserWithEmailAndPassword(auth, email, password);
    await sendEmailVerification(
      credential.user,
      getEmailVerificationActionCodeSettings()
    );
    return credential;
  }, []);

  const signInWithEmail = useCallback(async (email, password) => {
    return signInWithEmailAndPassword(auth, email, password);
  }, []);

  const signInWithGoogle = useCallback(async () => {
    try {
      console.log("Attempting Google Sign-In with popup...");
      return await signInWithPopup(auth, googleProvider);
    } catch (error) {
      console.error("Google popup sign-in failed:", error.code, error.message);
      const popupIssues = new Set([
        "auth/popup-blocked",
        "auth/popup-closed-by-user",
        "auth/cancelled-popup-request",
        "auth/operation-not-supported-in-this-environment",
      ]);
      if (popupIssues.has(error?.code)) {
        console.log("Environment issue or popup blocked. Attempting redirect...");
        try {
          await signInWithRedirect(auth, googleProvider);
        } catch (redirectError) {
          console.error("Google redirect sign-in failed:", redirectError.code, redirectError.message);
          if (redirectError.code === "auth/operation-not-supported-in-this-environment") {
            alert("Google Sign-In is not supported in this mobile environment via the Web SDK. Please use the native Capacitor Firebase plugin for Android support.");
          }
          throw redirectError;
        }
        return null;
      }
      throw error;
    }
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

  const changePassword = useCallback(async (currentPassword, newPassword) => {
    await changeUserPassword(currentPassword, newPassword);
    await reloadUser();
  }, [reloadUser]);

  const changeEmail = useCallback(async (currentPassword, newEmail) => {
    await changeUserEmail(currentPassword, newEmail);
  }, []);

  const resendVerificationEmail = useCallback(async () => {
    if (!auth.currentUser) {
      throw new Error("You must be signed in to resend the verification email.");
    }
    await sendEmailVerification(
      auth.currentUser,
      getEmailVerificationActionCodeSettings()
    );
  }, []);

  const resetEmailLinkVerification = useCallback(() => {
    setEmailLinkVerification(idleEmailLinkVerification);
  }, []);

  const logOut = useCallback(async () => {
    return signOut(auth);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading: loading || !redirectHandled,
      needsEmailVerification: needsEmailVerification(user),
      usesPasswordProvider: usesPasswordProvider(user),
      signUpWithEmail,
      signInWithEmail,
      signInWithGoogle,
      resendVerificationEmail,
      reloadUser,
      logOut,
      changePassword,
      changeEmail,
      emailLinkVerification,
      resetEmailLinkVerification,
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
      changePassword,
      changeEmail,
      emailLinkVerification,
      resetEmailLinkVerification,
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
