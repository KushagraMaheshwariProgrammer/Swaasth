import { deleteField, doc, getDoc, serverTimestamp, setDoc } from "firebase/firestore";
import { awaitFirestoreReady, db } from "../firebase";
import { TERMS_VERSION } from "../data/termsAndConditions";
import { MEDICAL_HISTORY_CONSENT_VERSION } from "../data/medicalHistoryConsent";
import {
  getLocalMedicalHistoryConsent,
  setLocalMedicalHistoryConsentAccepted,
  setLocalMedicalHistoryConsentDeclined,
  clearLocalMedicalHistoryConsent,
} from "./localMedicalHistoryConsentStore";
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
    await awaitFirestoreReady();
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

function isMedicalHistoryConsentAccepted(data) {
  return (
    Boolean(data?.medicalHistoryConsentAt) &&
    data?.medicalHistoryConsentVersion === MEDICAL_HISTORY_CONSENT_VERSION
  );
}

function isMedicalHistoryConsentDeclined(data) {
  return (
    Boolean(data?.medicalHistoryConsentDeclinedAt) &&
    !data?.medicalHistoryConsentAt &&
    data?.medicalHistoryConsentVersion === MEDICAL_HISTORY_CONSENT_VERSION
  );
}

export async function getMedicalHistoryConsent(userId) {
  const local = getLocalMedicalHistoryConsent(userId);
  if (local.accepted || local.declined) {
    return local;
  }

  try {
    await awaitFirestoreReady();
    const snapshot = await withTimeout(getDoc(userProfileRef(userId)));
    if (!snapshot.exists()) {
      return { accepted: false, declined: false, version: null };
    }
    const data = snapshot.data();
    if (isMedicalHistoryConsentAccepted(data)) {
      setLocalMedicalHistoryConsentAccepted(userId);
      return {
        accepted: true,
        declined: false,
        version: data.medicalHistoryConsentVersion ?? null,
      };
    }
    if (isMedicalHistoryConsentDeclined(data)) {
      setLocalMedicalHistoryConsentDeclined(userId);
      return {
        accepted: false,
        declined: true,
        version: data.medicalHistoryConsentVersion ?? null,
      };
    }
    return {
      accepted: false,
      declined: false,
      version: data.medicalHistoryConsentVersion ?? null,
    };
  } catch (error) {
    console.warn("Could not load medical history consent from Firestore:", error);
    return local;
  }
}

export async function acceptMedicalHistoryConsent(userId) {
  setLocalMedicalHistoryConsentAccepted(userId);

  try {
    await withTimeout(
      setDoc(
        userProfileRef(userId),
        {
          medicalHistoryConsentAt: serverTimestamp(),
          medicalHistoryConsentVersion: MEDICAL_HISTORY_CONSENT_VERSION,
          medicalHistoryConsentDeclinedAt: deleteField(),
        },
        { merge: true }
      )
    );
  } catch (error) {
    console.warn("Could not sync medical history consent to Firestore:", error);
  }
}

export async function declineMedicalHistoryConsent(userId) {
  setLocalMedicalHistoryConsentDeclined(userId);

  try {
    await withTimeout(
      setDoc(
        userProfileRef(userId),
        {
          medicalHistoryConsentDeclinedAt: serverTimestamp(),
          medicalHistoryConsentVersion: MEDICAL_HISTORY_CONSENT_VERSION,
          medicalHistoryConsentAt: deleteField(),
        },
        { merge: true }
      )
    );
  } catch (error) {
    console.warn("Could not sync medical history consent decline to Firestore:", error);
  }
}

export async function revokeMedicalHistoryConsent(userId) {
  clearLocalMedicalHistoryConsent(userId);

  try {
    await withTimeout(
      setDoc(
        userProfileRef(userId),
        {
          medicalHistoryConsentAt: deleteField(),
          medicalHistoryConsentDeclinedAt: deleteField(),
          medicalHistoryConsentVersion: deleteField(),
        },
        { merge: true }
      )
    );
  } catch (error) {
    console.warn("Could not revoke medical history consent in Firestore:", error);
  }
}
