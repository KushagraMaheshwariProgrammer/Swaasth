import { Capacitor } from "@capacitor/core";
import { initializeApp } from "firebase/app";
import {
  getAuth,
  indexedDBLocalPersistence,
  initializeAuth,
} from "firebase/auth";
import {
  doc,
  getFirestore,
  initializeFirestore,
  onSnapshot,
  persistentLocalCache,
} from "firebase/firestore";
import { getFirebaseConfig } from "./firebaseConfig";

const firebaseConfig = getFirebaseConfig();

const missingKeys = Object.entries(firebaseConfig)
  .filter(([key, value]) => key !== "measurementId" && !value)
  .map(([key]) => key);

if (missingKeys.length) {
  console.error("Missing Firebase config keys:", missingKeys);
  throw new Error(
    `Missing Firebase config: ${missingKeys.join(", ")}. Check frontend/google-services.json.`
  );
}

const app = initializeApp(firebaseConfig);

function createAuth() {
  if (Capacitor.isNativePlatform()) {
    return initializeAuth(app, {
      persistence: indexedDBLocalPersistence,
    });
  }
  return getAuth(app);
}

export const auth = createAuth();

function createFirestore() {
  if (Capacitor.isNativePlatform()) {
    return initializeFirestore(app, {
      localCache: persistentLocalCache(),
    });
  }
  return getFirestore(app);
}

export const db = createFirestore();

let anchorUnsubscribe = null;
let firestoreReadyPromise = Promise.resolve();

/** Keep a long-lived listen target open to avoid Firestore SDK ca9/b815 races. */
export function anchorFirestoreSession(userId) {
  if (anchorUnsubscribe) {
    anchorUnsubscribe();
    anchorUnsubscribe = null;
  }

  if (!userId) {
    firestoreReadyPromise = Promise.resolve();
    return firestoreReadyPromise;
  }

  let settled = false;
  firestoreReadyPromise = new Promise((resolve) => {
    const finish = () => {
      if (!settled) {
        settled = true;
        resolve();
      }
    };

    const userRef = doc(db, "users", userId);
    anchorUnsubscribe = onSnapshot(userRef, finish, (error) => {
      console.warn("Firestore session anchor listener error:", error);
      finish();
    });
  });

  return firestoreReadyPromise;
}

export function awaitFirestoreReady() {
  return firestoreReadyPromise;
}
