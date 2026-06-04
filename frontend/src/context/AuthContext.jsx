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
  getMultiFactorResolver,
  getRedirectResult,
  GoogleAuthProvider,
  onAuthStateChanged,
  sendEmailVerification,
  signInWithEmailAndPassword,
  signInWithPopup,
  signInWithRedirect,
  signOut,
  TotpMultiFactorGenerator,
} from "firebase/auth";
import {
  changeUserEmail,
  changeUserPassword,
  enrollTotpMfa,
  generateTotpEnrollment,
  getTotpFactors,
  hasTotpMfa,
  reauthenticateCurrentUser,
  unenrollTotpMfa,
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
  const [mfaResolver, setMfaResolver] = useState(null);

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
    try {
      return await signInWithEmailAndPassword(auth, email, password);
    } catch (error) {
      if (error?.code === "auth/multi-factor-auth-required") {
        setMfaResolver(getMultiFactorResolver(auth, error));
      }
      throw error;
    }
  }, []);

  const signInWithGoogle = useCallback(async () => {
    try {
      return await signInWithPopup(auth, googleProvider);
    } catch (error) {
      if (error?.code === "auth/multi-factor-auth-required") {
        setMfaResolver(getMultiFactorResolver(auth, error));
        throw error;
      }
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

  const completeMfaSignIn = useCallback(async (verificationCode) => {
    if (!mfaResolver) {
      throw new Error("No two-factor sign-in is in progress.");
    }
    const totpHint = mfaResolver.hints.find(
      (hint) => hint.factorId === TotpMultiFactorGenerator.FACTOR_ID
    );
    if (!totpHint) {
      throw new Error("Unsupported second factor. Use an authenticator app.");
    }
    const assertion = TotpMultiFactorGenerator.assertionForSignIn(
      totpHint.uid,
      verificationCode.trim()
    );
    const credential = await mfaResolver.resolveSignIn(assertion);
    setMfaResolver(null);
    return credential;
  }, [mfaResolver]);

  const cancelMfaSignIn = useCallback(() => {
    setMfaResolver(null);
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

  const startTotpEnrollment = useCallback(async (currentPassword) => {
    await reauthenticateCurrentUser(currentPassword);
    return generateTotpEnrollment();
  }, []);

  const finishTotpEnrollment = useCallback(async (totpSecret, verificationCode) => {
    await enrollTotpMfa(totpSecret, verificationCode);
    await reloadUser();
  }, [reloadUser]);

  const removeTotpMfa = useCallback(async (factorUid, currentPassword) => {
    await unenrollTotpMfa(factorUid, currentPassword);
    await reloadUser();
  }, [reloadUser]);

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
    setMfaResolver(null);
    return signOut(auth);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading: loading || !redirectHandled,
      needsEmailVerification: needsEmailVerification(user),
      usesPasswordProvider: usesPasswordProvider(user),
      hasTotpMfa: hasTotpMfa(user),
      totpFactors: getTotpFactors(user),
      mfaResolver,
      signUpWithEmail,
      signInWithEmail,
      signInWithGoogle,
      completeMfaSignIn,
      cancelMfaSignIn,
      resendVerificationEmail,
      reloadUser,
      logOut,
      changePassword,
      changeEmail,
      startTotpEnrollment,
      finishTotpEnrollment,
      removeTotpMfa,
      emailLinkVerification,
      resetEmailLinkVerification,
    }),
    [
      user,
      loading,
      redirectHandled,
      mfaResolver,
      signUpWithEmail,
      signInWithEmail,
      signInWithGoogle,
      completeMfaSignIn,
      cancelMfaSignIn,
      resendVerificationEmail,
      reloadUser,
      logOut,
      changePassword,
      changeEmail,
      startTotpEnrollment,
      finishTotpEnrollment,
      removeTotpMfa,
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
