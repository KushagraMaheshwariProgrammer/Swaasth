import { Capacitor } from "@capacitor/core";
import { initializeApp } from "firebase/app";
import {
  getAuth,
  indexedDBLocalPersistence,
  initializeAuth,
} from "firebase/auth";
import {
  getFirestore,
  initializeFirestore,
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
