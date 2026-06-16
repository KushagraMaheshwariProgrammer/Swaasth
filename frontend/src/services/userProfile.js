import { doc, getDoc, serverTimestamp, setDoc } from "firebase/firestore";
import { db } from "../firebase";
import { TERMS_VERSION } from "../data/termsAndConditions";
import {
  getLocalTermsAcceptance,
  setLocalTermsAcceptance,
} from "./localTermsStore";

const FIRESTORE_TIMEOUT_MS = 5000;

function userProfileRef(userId) {
  return doc(db, "users", userId);
}

function withTimeout(promise, ms = FIRESTORE_TIMEOUT_MS) {
  return Promise.race([
    promise,
    new Promise((_, reject) => {
      window.setTimeout(() => reject(new Error("Terms sync timed out.")), ms);
    }),
  ]);
}

function isAcceptedRecord(data) {
  return Boolean(data?.termsAcceptedAt) && data?.termsVersion === TERMS_VERSION;
}

export async function getTermsAcceptance(userId) {
  const local = getLocalTermsAcceptance(userId);
  if (local.accepted) {
    return local;
  }

  try {
    const snapshot = await withTimeout(getDoc(userProfileRef(userId)));
    if (!snapshot.exists()) {
      return { accepted: false, version: null };
    }
    const data = snapshot.data();
    const accepted = isAcceptedRecord(data);
    if (accepted) {
      setLocalTermsAcceptance(userId);
    }
    return {
      accepted,
      version: data.termsVersion ?? null,
    };
  } catch (error) {
    console.warn("Could not load terms acceptance from Firestore:", error);
    return local;
  }
}

export async function acceptTerms(userId) {
  setLocalTermsAcceptance(userId);

  try {
    await withTimeout(
      setDoc(
        userProfileRef(userId),
        {
          termsAcceptedAt: serverTimestamp(),
          termsVersion: TERMS_VERSION,
        },
        { merge: true }
      )
    );
  } catch (error) {
    console.warn("Could not sync terms acceptance to Firestore:", error);
  }
}
