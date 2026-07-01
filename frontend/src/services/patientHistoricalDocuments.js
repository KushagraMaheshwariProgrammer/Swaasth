import {
  collection,
  deleteDoc,
  doc,
  getDocs,
  serverTimestamp,
  setDoc,
} from "firebase/firestore";
import { db } from "../firebase";
import { getApiBase } from "./apiBase";
import { fetchBackend, parseJsonResponse } from "./httpUtils";
import {
  normalizePrescriptionPayload,
  uploadClinicalDocument,
  uploadPrescription,
} from "./prescriptions";
import { sanitizeForFirestore } from "./bills";

import { canSaveMedicalHistory } from "../utils/medicalHistoryConsent";

const STORAGE_KEY = "swaasth_local_historical_docs_v1";

function readStore() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { users: {} };
    }
    const parsed = JSON.parse(raw);
    return parsed?.users ? parsed : { users: {} };
  } catch {
    return { users: {} };
  }
}

function writeStore(store) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
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

async function uploadBillWithoutLocation(file) {
  const formData = new FormData();
  formData.append("file", file);
  const params = new URLSearchParams({
    city: "Unknown",
    hospital_type: "general",
  });
  const response = await fetchBackend(
    `${getApiBase()}/upload-bill?${params}`,
    {
      method: "POST",
      body: formData,
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
      ocr_text: payload.ocr_text || "",
    };
  }

  if (documentType === "bill") {
    return {
      diagnosis: payload.diagnosis || "",
      line_items: payload.line_items || [],
      ocr_text: payload.ocr_text || "",
    };
  }

  return {
    diagnosis: payload.diagnosis || "",
    clinical_context: payload.clinical_context || {},
    symptoms: payload.clinical_context?.symptoms || payload.symptoms || [],
    test_results: payload.clinical_context?.test_results || [],
    procedures: payload.procedures || [],
    ocr_text: payload.ocr_text || "",
  };
}

export async function extractHistoricalDocument(file, documentType) {
  if (documentType === "prescription") {
    return uploadPrescription(file);
  }
  if (documentType === "bill") {
    return uploadBillWithoutLocation(file);
  }
  return uploadClinicalDocument(file, documentType);
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
  } = documentInput;

  if (!documentType || !documentDate) {
    throw new Error("Document type and date are required.");
  }

  const documentData = {
    patientId,
    filename: filename || file?.name || "document",
    documentType,
    documentDate,
    extractedSummary: extractedSummary || {},
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
      const snapshot = await getDocs(historicalDocsCollection(userId, patientId));
      await Promise.all(snapshot.docs.map((entry) => deleteDoc(entry.ref)));
    } catch (error) {
      console.error("Failed to delete cloud historical documents:", error);
    }
  }
}
