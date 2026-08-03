import {
  collection,
  deleteDoc,
  doc,
  getDocs,
  serverTimestamp,
  setDoc,
} from "firebase/firestore";
import { awaitFirestoreReady, db } from "../firebase";
import { getApiBase } from "./apiBase";
import { fetchBackend, parseJsonResponse, LONG_FETCH_TIMEOUT_MS } from "./httpUtils";
import {
  normalizePrescriptionPayload,
  uploadClinicalDocument,
  uploadPrescription,
} from "./prescriptions";
import { sanitizeForFirestore, stripOcrText } from "./bills";
import { enrichDocumentUploadError } from "../utils/documentBundle";

import { canSaveMedicalHistory } from "../utils/medicalHistoryConsent";
import { getSecureJson, setSecureJson } from "./secureLocalStore";

const STORAGE_KEY = "swaasth_local_historical_docs_v1";

function readStore() {
  const parsed = getSecureJson(STORAGE_KEY, { users: {} });
  return parsed?.users ? parsed : { users: {} };
}

function writeStore(store) {
  setSecureJson(STORAGE_KEY, store);
}

function userEntries(store, userId) {
  if (!store.users[userId]) {
    store.users[userId] = [];
  }
  return store.users[userId];
}

function historicalDocsCollection(userId, patientId) {
  return collection(db, "users", userId, "patients", patientId, "historical_documents");
}

function historicalDocRef(userId, patientId, docId) {
  return doc(db, "users", userId, "patients", patientId, "historical_documents", docId);
}

function localDocToEntry(entry) {
  return {
    id: entry.firestoreId || entry.localId,
    localId: entry.localId,
    firestoreId: entry.firestoreId || null,
    localOnly: !entry.firestoreId,
    ...entry.documentData,
  };
}

function sortByDocumentDate(docs) {
  return [...docs].sort((left, right) => {
    const leftTime = new Date(left.documentDate || 0).getTime();
    const rightTime = new Date(right.documentDate || 0).getTime();
    return rightTime - leftTime;
  });
}

function collectPatientIdSet(patientIds) {
  return new Set(patientIds.filter(Boolean));
}

export function getLocalHistoricalDocuments(userId, patientIds) {
  const idSet = collectPatientIdSet(patientIds);
  if (!userId || !idSet.size) {
    return [];
  }
  const entries = readStore().users[userId] || [];
  return sortByDocumentDate(
    entries
      .filter((entry) => idSet.has(entry.documentData?.patientId))
      .map((entry) => localDocToEntry(entry))
  );
}

async function fetchCloudHistoricalDocuments(userId, patientIds) {
  await awaitFirestoreReady();
  const ids = [...collectPatientIdSet(patientIds)].slice(0, 10);
  if (!ids.length) {
    return [];
  }

  const results = [];
  for (const patientId of ids) {
    try {
      const snapshot = await getDocs(historicalDocsCollection(userId, patientId));
      for (const entry of snapshot.docs) {
        results.push({
          id: entry.id,
          firestoreId: entry.id,
          localOnly: false,
          patientId,
          ...entry.data(),
        });
      }
    } catch (error) {
      console.error("Failed to load historical documents from Firebase:", error);
    }
  }
  return sortByDocumentDate(results);
}

function mergeHistoricalDocumentLists(cloudDocs, localEntries) {
  const cloudIds = new Set(cloudDocs.map((doc) => doc.id));
  const merged = [...cloudDocs];

  for (const entry of localEntries) {
    if (entry.firestoreId && cloudIds.has(entry.firestoreId)) {
      continue;
    }
    const publicId = entry.firestoreId || entry.localId;
    if (!merged.some((doc) => doc.id === publicId)) {
      merged.push(entry);
    }
  }

  return sortByDocumentDate(merged);
}

export async function getPatientHistoricalDocuments(userId, patientId) {
  if (!userId || !patientId) {
    return [];
  }

  const localEntries = getLocalHistoricalDocuments(userId, [patientId]);
  let cloudDocs = [];
  try {
    cloudDocs = await fetchCloudHistoricalDocuments(userId, [patientId]);
  } catch (error) {
    console.error("Failed to fetch cloud historical documents:", error);
  }

  return mergeHistoricalDocumentLists(cloudDocs, localEntries);
}

async function uploadBillWithLocation(file, { state, city, hospitalName }) {
  const formData = new FormData();
  formData.append("file", file);
  const params = new URLSearchParams({
    state_ut_name: state || "Unknown",
    city: city || "Unknown",
    hospital_type: "general",
  });
  if (hospitalName) {
    params.set("hospital_name", hospitalName);
  }
  const response = await fetchBackend(
    `${getApiBase()}/upload-bill?${params}`,
    {
      method: "POST",
      body: formData,
      timeoutMs: LONG_FETCH_TIMEOUT_MS,
    }
  );
  return parseJsonResponse(response);
}

export function buildExtractedSummary(documentType, payload) {
  if (!payload) {
    return {};
  }

  if (documentType === "prescription") {
    const normalized = normalizePrescriptionPayload(payload);
    return {
      diagnosis: normalized.diagnosis || "",
      symptoms: normalized.clinicalContext?.symptoms || [],
      test_results: normalized.clinicalContext?.test_results || [],
      medicines: normalized.medicines || [],
      tests: normalized.tests || [],
      procedures: normalized.procedures || [],
    };
  }

  if (documentType === "bill") {
    return {
      diagnosis: payload.diagnosis || "",
      line_items: payload.line_items || [],
    };
  }

  return {
    diagnosis: payload.diagnosis || "",
    clinical_context: payload.clinical_context || {},
    symptoms: payload.clinical_context?.symptoms || payload.symptoms || [],
    test_results: payload.clinical_context?.test_results || [],
    procedures: payload.procedures || [],
  };
}

export async function extractHistoricalDocument(file, documentType, hospital = null) {
  const doc = { file, documentType };
  try {
    if (documentType === "prescription") {
      return uploadPrescription(file);
    }
    if (documentType === "bill") {
      return uploadBillWithLocation(file, {
        state: hospital?.state || "Unknown",
        city: hospital?.city || "Unknown",
        hospitalName: hospital?.name || "",
      });
    }
    return uploadClinicalDocument(file, documentType);
  } catch (error) {
    throw enrichDocumentUploadError(error, doc);
  }
}

function persistLocalHistoricalDocument(userId, documentData) {
  const store = readStore();
  const entries = userEntries(store, userId);
  const localId =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `local-hist-${Date.now()}-${Math.random().toString(36).slice(2)}`;

  entries.push({
    localId,
    documentData,
    synced: false,
    firestoreId: null,
    updatedAt: Date.now(),
  });
  writeStore(store);
  return localId;
}

function markLocalHistoricalDocumentSynced(userId, localId, firestoreId) {
  const store = readStore();
  const entries = store.users[userId] || [];
  const entry = entries.find((item) => item.localId === localId);
  if (entry) {
    entry.firestoreId = firestoreId;
    entry.synced = true;
    writeStore(store);
  }
}

function removeLocalHistoricalDocument(userId, documentId) {
  const store = readStore();
  const entries = store.users[userId] || [];
  store.users[userId] = entries.filter(
    (entry) => entry.localId !== documentId && entry.firestoreId !== documentId
  );
  writeStore(store);
}

async function pushHistoricalDocumentToCloud(userId, patientId, docId, documentData) {
  const payload = sanitizeForFirestore({
    ...documentData,
    updatedAt: serverTimestamp(),
    createdAt: serverTimestamp(),
  });
  await setDoc(historicalDocRef(userId, patientId, docId), payload, { merge: true });
  markLocalHistoricalDocumentSynced(userId, docId, docId);
}

export async function saveHistoricalDocument(userId, patientId, documentInput, options = {}) {
  if (!userId || !patientId) {
    throw new Error("Missing user or patient.");
  }

  if (
    options.accountConsent != null &&
    options.patient != null &&
    !canSaveMedicalHistory(options.accountConsent, options.patient)
  ) {
    throw new Error("Medical history consent is required to save documents.");
  }

  const {
    file,
    documentType,
    documentDate,
    extractedSummary,
    filename,
    hospitalId,
    hospitalName,
    hospitalCity,
    hospitalState,
  } = documentInput;

  if (!documentType || !documentDate) {
    throw new Error("Document type and date are required.");
  }
  if (!hospitalId) {
    throw new Error("Select a hospital before saving this document.");
  }

  const documentData = {
    patientId,
    filename: filename || file?.name || "document",
    documentType,
    documentDate,
    extractedSummary: stripOcrText(extractedSummary || {}),
    hospitalId,
    hospitalName: hospitalName || "",
    hospitalCity: hospitalCity || "",
    hospitalState: hospitalState || "",
  };

  const localId = persistLocalHistoricalDocument(userId, documentData);

  pushHistoricalDocumentToCloud(userId, patientId, localId, documentData).catch(
    (error) => {
      console.error("Background historical document cloud sync failed:", error);
    }
  );

  return {
    id: localId,
    localId,
    localOnly: true,
    ...documentData,
  };
}

export async function deleteHistoricalDocument(userId, patientId, documentId) {
  if (!userId || !patientId || !documentId) {
    throw new Error("Missing document details.");
  }

  removeLocalHistoricalDocument(userId, documentId);

  try {
    await deleteDoc(historicalDocRef(userId, patientId, documentId));
  } catch (error) {
    const code = error?.code || "";
    if (code !== "not-found") {
      console.error("Cloud historical document delete failed:", error);
    }
  }
}

export async function deleteHistoricalDocumentsForPatientIds(userId, patientIds) {
  if (!userId) {
    return;
  }
  const docs = getLocalHistoricalDocuments(userId, patientIds);
  for (const entry of docs) {
    removeLocalHistoricalDocument(userId, entry.id);
  }

  for (const patientId of patientIds) {
    try {
      await awaitFirestoreReady();
      const snapshot = await getDocs(historicalDocsCollection(userId, patientId));
      await Promise.all(snapshot.docs.map((entry) => deleteDoc(entry.ref)));
    } catch (error) {
      console.error("Failed to delete cloud historical documents:", error);
    }
  }
}

export function clearLocalHistoricalDocumentsForUser(userId) {
  if (!userId) {
    return;
  }
  const store = readStore();
  if (store.users[userId]) {
    delete store.users[userId];
    writeStore(store);
  }
}

export async function deleteAllHistoricalDocumentsForUser(userId, patientIds = []) {
  if (!userId) {
    return;
  }
  clearLocalHistoricalDocumentsForUser(userId);
  const ids = [...new Set(patientIds.filter(Boolean))];
  for (const patientId of ids) {
    try {
      await awaitFirestoreReady();
      const snapshot = await getDocs(historicalDocsCollection(userId, patientId));
      await Promise.all(snapshot.docs.map((entry) => deleteDoc(entry.ref)));
    } catch (error) {
      console.error("Failed to delete cloud historical documents:", error);
    }
  }
}
