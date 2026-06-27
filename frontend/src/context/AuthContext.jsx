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
  signOut,
} from "firebase/auth";
import {
  changeUserEmail,
  changeUserPassword,
  usesPasswordProvider,
} from "../auth/accountSecurity";
import { signInWithGoogle as performGoogleSignIn } from "../auth/googleSignIn";
import {
  clearEmailVerificationLinkParams,
  getEmailVerificationActionCodeSettings,
  getEmailVerificationLinkParams,
  getVerificationErrorMessage,
} from "../auth/emailVerification";
import { ensureFirebaseWebAuth } from "../auth/ensureFirebaseWebAuth";
import { auth } from "../firebase";
import { syncPendingBills } from "../services/bills";
import { syncPendingPatients } from "../services/patients";
import {
  acceptTerms as persistTermsAcceptance,
  getTermsAcceptance,
} from "../services/userProfile";

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
  const [termsAccepted, setTermsAccepted] = useState(null);
  const [termsLoading, setTermsLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const bootstrapAuth = async () => {
      try {
        await ensureFirebaseWebAuth();
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

    const unsubscribe = onAuthStateChanged(auth, async (nextUser) => {
      setUser(nextUser);
      setLoading(false);
      if (nextUser && !needsEmailVerification(nextUser)) {
        await ensureFirebaseWebAuth();
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
    if (!user || needsEmailVerification(user)) {
      setTermsAccepted(null);
      setTermsLoading(false);
      return undefined;
    }

    let cancelled = false;
    setTermsLoading(true);

    getTermsAcceptance(user.uid)
      .then(({ accepted }) => {
        if (!cancelled) {
          setTermsAccepted(accepted);
        }
      })
      .catch((error) => {
        console.error("Failed to load terms acceptance:", error);
        if (!cancelled) {
          setTermsAccepted(false);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setTermsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [user]);

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
    return performGoogleSignIn(auth, googleProvider);
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

  const acceptTerms = useCallback(async () => {
    if (!auth.currentUser) {
      throw new Error("You must be signed in to accept the Terms and Conditions.");
    }
    await persistTermsAcceptance(auth.currentUser.uid);
    setTermsAccepted(true);
  }, []);

  const logOut = useCallback(async () => {
    return signOut(auth);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading: loading || !redirectHandled,
      needsEmailVerification: needsEmailVerification(user),
      termsAccepted,
      termsLoading,
      acceptTerms,
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
      termsAccepted,
      termsLoading,
      acceptTerms,
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
