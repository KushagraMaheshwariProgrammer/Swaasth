/**
 * AES-GCM encrypted localStorage for PHI mirrors.
 *
 * - CryptoKey (non-extractable) lives in IndexedDB
 * - Decrypted values are held in an in-memory cache for sync reads
 * - Writes update the cache immediately and persist encrypted asynchronously
 * - One-time migration copies legacy plaintext keys into encrypted storage
 */

const IDB_NAME = "swaasth_secure_store";
const IDB_VERSION = 1;
const IDB_KEY_STORE = "keys";
const CRYPTO_KEY_ID = "aes-gcm-v1";
const ENCRYPTED_PREFIX = "swaasth_enc_v1:";
const IV_BYTES = 12;

const LEGACY_PLAINTEXT_KEYS = [
  "swaasth_local_bills_v1",
  "swaasth_local_patients_v1",
  "swaasth_local_historical_docs_v1",
  "swaasth_local_hospitals_v1",
  "swaasth_medical_history_consent_v1",
  "swaasth_terms_acceptance_v1",
];

const LEGACY_PREFIXES = ["swaasth_question_responses_"];

/** @type {Map<string, unknown>} */
const memoryCache = new Map();

/** @type {CryptoKey | null} */
let cryptoKey = null;

/** @type {Promise<void> | null} */
let initPromise = null;

let ready = false;

function openKeyDb() {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB is unavailable."));
      return;
    }
    const request = indexedDB.open(IDB_NAME, IDB_VERSION);
    request.onerror = () => reject(request.error || new Error("IndexedDB open failed."));
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(IDB_KEY_STORE)) {
        db.createObjectStore(IDB_KEY_STORE);
      }
    };
    request.onsuccess = () => resolve(request.result);
  });
}

function idbGet(db, key) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(IDB_KEY_STORE, "readonly");
    const store = tx.objectStore(IDB_KEY_STORE);
    const request = store.get(key);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
  });
}

function idbPut(db, key, value) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(IDB_KEY_STORE, "readwrite");
    const store = tx.objectStore(IDB_KEY_STORE);
    const request = store.put(value, key);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

function bytesToBase64(bytes) {
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

function base64ToBytes(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

async function generateAndStoreKey(db) {
  const key = await crypto.subtle.generateKey(
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
  await idbPut(db, CRYPTO_KEY_ID, key);
  return key;
}

async function loadOrCreateKey() {
  const db = await openKeyDb();
  try {
    const existing = await idbGet(db, CRYPTO_KEY_ID);
    if (existing) {
      return existing;
    }
    return await generateAndStoreKey(db);
  } finally {
    db.close();
  }
}

async function encryptPayload(plaintext) {
  if (!cryptoKey) {
    throw new Error("Secure store is not initialized.");
  }
  const iv = crypto.getRandomValues(new Uint8Array(IV_BYTES));
  const encoded = new TextEncoder().encode(plaintext);
  const cipherBuffer = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    cryptoKey,
    encoded
  );
  return JSON.stringify({
    v: 1,
    iv: bytesToBase64(iv),
    ct: bytesToBase64(new Uint8Array(cipherBuffer)),
  });
}

async function decryptPayload(envelopeJson) {
  if (!cryptoKey) {
    throw new Error("Secure store is not initialized.");
  }
  const envelope = JSON.parse(envelopeJson);
  if (!envelope?.iv || !envelope?.ct) {
    throw new Error("Invalid encrypted payload.");
  }
  const iv = base64ToBytes(envelope.iv);
  const cipherBytes = base64ToBytes(envelope.ct);
  const plainBuffer = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv },
    cryptoKey,
    cipherBytes
  );
  return new TextDecoder().decode(plainBuffer);
}

function encryptedStorageKey(logicalKey) {
  return `${ENCRYPTED_PREFIX}${logicalKey}`;
}

async function persistEncrypted(logicalKey, value) {
  if (typeof localStorage === "undefined") {
    return;
  }
  const plaintext = JSON.stringify(value);
  const encrypted = await encryptPayload(plaintext);
  localStorage.setItem(encryptedStorageKey(logicalKey), encrypted);
}

async function loadEncryptedIntoCache(logicalKey) {
  if (typeof localStorage === "undefined") {
    return false;
  }
  const raw = localStorage.getItem(encryptedStorageKey(logicalKey));
  if (!raw) {
    return false;
  }
  try {
    const plaintext = await decryptPayload(raw);
    memoryCache.set(logicalKey, JSON.parse(plaintext));
    return true;
  } catch (error) {
    console.warn(`Failed to decrypt secure store key ${logicalKey}:`, error);
    return false;
  }
}

function collectLegacyKeys() {
  if (typeof localStorage === "undefined") {
    return [];
  }
  const keys = new Set(LEGACY_PLAINTEXT_KEYS);
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (!key) {
      continue;
    }
    if (key.startsWith(ENCRYPTED_PREFIX)) {
      continue;
    }
    for (const prefix of LEGACY_PREFIXES) {
      if (key.startsWith(prefix)) {
        keys.add(key);
      }
    }
  }
  return [...keys];
}

async function migrateLegacyPlaintext() {
  if (typeof localStorage === "undefined") {
    return;
  }
  for (const logicalKey of collectLegacyKeys()) {
    const raw = localStorage.getItem(logicalKey);
    if (raw == null) {
      continue;
    }
    try {
      let value;
      try {
        value = JSON.parse(raw);
      } catch {
        value = raw;
      }
      memoryCache.set(logicalKey, value);
      await persistEncrypted(logicalKey, value);
      localStorage.removeItem(logicalKey);
    } catch (error) {
      console.warn(`Failed to migrate plaintext key ${logicalKey}:`, error);
    }
  }
}

async function hydrateEncryptedKeys() {
  if (typeof localStorage === "undefined") {
    return;
  }
  const logicalKeys = [];
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (key?.startsWith(ENCRYPTED_PREFIX)) {
      logicalKeys.push(key.slice(ENCRYPTED_PREFIX.length));
    }
  }
  await Promise.all(logicalKeys.map((logicalKey) => loadEncryptedIntoCache(logicalKey)));
}

/**
 * Must be awaited once at app startup before any sync store reads.
 */
export function initSecureLocalStore() {
  if (initPromise) {
    return initPromise;
  }
  initPromise = (async () => {
    if (typeof window === "undefined" || !window.crypto?.subtle) {
      console.warn("Web Crypto unavailable; secure local store will use memory only.");
      ready = true;
      return;
    }
    try {
      cryptoKey = await loadOrCreateKey();
      await hydrateEncryptedKeys();
      await migrateLegacyPlaintext();
    } catch (error) {
      console.error("Secure local store initialization failed:", error);
    } finally {
      ready = true;
    }
  })();
  return initPromise;
}

export function isSecureLocalStoreReady() {
  return ready;
}

export function getSecureJson(key, fallback = null) {
  if (memoryCache.has(key)) {
    return memoryCache.get(key);
  }
  return fallback;
}

export function setSecureJson(key, value) {
  memoryCache.set(key, value);
  if (!cryptoKey) {
    return;
  }
  void persistEncrypted(key, value).catch((error) => {
    console.warn(`Failed to persist encrypted key ${key}:`, error);
  });
}

export function removeSecureItem(key) {
  memoryCache.delete(key);
  if (typeof localStorage !== "undefined") {
    localStorage.removeItem(encryptedStorageKey(key));
    localStorage.removeItem(key);
  }
}

export function clearSecureKeysMatching(prefix) {
  const toRemove = [];
  for (const key of memoryCache.keys()) {
    if (key.startsWith(prefix)) {
      toRemove.push(key);
    }
  }
  for (const key of toRemove) {
    removeSecureItem(key);
  }
  if (typeof localStorage === "undefined") {
    return;
  }
  const leftover = [];
  for (let i = 0; i < localStorage.length; i += 1) {
    const storageKey = localStorage.key(i);
    if (!storageKey) {
      continue;
    }
    if (storageKey.startsWith(ENCRYPTED_PREFIX)) {
      const logical = storageKey.slice(ENCRYPTED_PREFIX.length);
      if (logical.startsWith(prefix)) {
        leftover.push(storageKey);
      }
    } else if (storageKey.startsWith(prefix)) {
      leftover.push(storageKey);
    }
  }
  for (const storageKey of leftover) {
    localStorage.removeItem(storageKey);
  }
}

export function listSecureKeysMatching(prefix) {
  const keys = new Set();
  for (const key of memoryCache.keys()) {
    if (key.startsWith(prefix)) {
      keys.add(key);
    }
  }
  return [...keys];
}
