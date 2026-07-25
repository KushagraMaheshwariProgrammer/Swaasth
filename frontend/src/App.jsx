import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  BrowserRouter,
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import BillResults from "./components/BillResults";
import BackLink from "./components/BackLink";
import { patientAgeApiPayload, formatPatientAge } from "./utils/patientAge";
import { getComparisonSchemeCopy, HOSPITAL_TYPE_OPTIONS } from "./billUtils";
import { AuthProvider, useAuth } from "./context/AuthContext";
import LoginPage from "./pages/LoginPage";
import HistoryPage from "./pages/HistoryPage";
import TakeActionPage from "./pages/TakeActionPage";
import PatientsPage from "./pages/PatientsPage";
import AccountSettingsPage from "./pages/AccountSettingsPage";
import VerifyEmailPage from "./pages/VerifyEmailPage";
import TermsDevPreview from "./pages/TermsDevPreview";
import UserNav from "./components/UserNav";
import PatientList from "./components/PatientList";
import HospitalList from "./components/HospitalList";
import ClinicalContextForm from "./components/ClinicalContextForm";
import DiagnosisPrompt from "./components/DiagnosisPrompt";
import PrescriptionResults from "./components/PrescriptionResults";
import TermsAndConditionsModal from "./components/TermsAndConditionsModal";
import MedicalHistoryConsentModal from "./components/MedicalHistoryConsentModal";
import MultiDocumentUpload from "./components/MultiDocumentUpload";
import BundleExtractionReview from "./components/BundleExtractionReview";
import DocumentDatePrompt from "./components/DocumentDatePrompt";
import MedicalHistoryConsentPage from "./pages/MedicalHistoryConsentPage";
import AppBackground from "./components/AppBackground";
import AndroidBackButtonHandler from "./components/AndroidBackButtonHandler";
import { getApiBase } from "./services/apiBase";
import {
  backendUnreachableMessage,
  fetchBackend,
  LONG_FETCH_TIMEOUT_MS,
  parseJsonResponse,
} from "./services/httpUtils";
import { getPatients, getPatientsLocalSnapshot } from "./services/patients";
import { resolveResultsView } from "./data/reportExport";
import { saveReportToAccount, mergeSavedReportIds } from "./services/bills";
import {
  analyzeTreatment,
  clinicalContextToApiPayload,
  emptyClinicalContext,
  hasClinicalData,
} from "./services/prescriptions";
import {
  resolveCanonicalStateUtName,
} from "./services/locations";
import {
  getLocalHospitalsSnapshot,
  getPatientHospitals,
  resolveHospitalLocation,
} from "./services/patientHospitals";
import {
  allBundleDocumentsConfirmed,
  bundleHasBills,
  bundleHasExtractedData,
  createBundleSession,
  formatUnconfirmedDocumentsMessage,
  mergeConfirmedDatesIntoBundle,
  processDocumentBundle,
} from "./utils/documentBundle";
import { itemsMissingDates } from "./utils/documentDates";
import {
  attachExtractionsToDocuments,
  mergeEditedExtractionsToBundle,
} from "./utils/documentExtraction";
import { buildPatientHistoryPayload } from "./utils/patientClinicalHistory";
import { resolveAccountConsent } from "./utils/medicalHistoryConsent";

function formatExtractionWarnings(warnings) {
  if (!warnings?.length) {
    return "";
  }
  if (warnings.length === 1) {
    return `We could not use one document (${warnings[0]}). Analysis will continue with the other uploaded data.`;
  }
  return `We could not use ${warnings.length} document(s): ${warnings.join(" ")} Analysis will continue with the available data.`;
}

function buildBundleExtractionInfo(merged) {
  const hasBillLineItems = merged.lineItems?.length > 0;
  const hasRxItems =
    merged.medicines?.length ||
    merged.tests?.length ||
    merged.procedures?.length;
  const messages = [];

  if (hasBillLineItems) {
    messages.push(
      `Extracted ${merged.lineItems.length} bill item${
        merged.lineItems.length === 1 ? "" : "s"
      } from your upload.`
    );
  } else if (hasRxItems) {
    messages.push(
      `Extracted ${merged.medicines?.length || 0} medicine(s), ${
        merged.tests?.length || 0
      } test(s), and ${merged.procedures?.length || 0} procedure(s).`
    );
  } else if (bundleHasExtractedData(merged)) {
    messages.push("Extracted clinical data from your upload.");
  }

  const warningMessage = formatExtractionWarnings(merged.extractionWarnings);
  if (warningMessage) {
    messages.push(warningMessage);
  }

  return messages.join(" ");
}

function formatFetchError(err, fallback) {
  if (err?.message === "Failed to fetch") {
    return backendUnreachableMessage();
  }
  return err?.message || fallback;
}

const CATEGORY_OPTIONS = [
  { id: "medicine", label: "Medicine" },
  { id: "test", label: "Test" },
  { id: "procedure", label: "Procedure" },
  { id: "other", label: "Other" },
];

const createEmptyLineItem = () => ({
  item_name: "",
  quantity: 1,
  unit_price: 0,
  total_price: 0,
  category: "other",
});

const normalizeLineItem = (item) => {
  const category = CATEGORY_OPTIONS.some((c) => c.id === item?.category)
    ? item.category
    : "other";
  const quantity = Math.max(Number(item?.quantity) || 0, 0);
  const unitPrice = Math.max(Number(item?.unit_price) || 0, 0);
  let totalPrice = Math.max(Number(item?.total_price) || 0, 0);
  if (totalPrice <= 0 && quantity > 0 && unitPrice > 0) {
    totalPrice = Math.round(quantity * unitPrice * 100) / 100;
  }
  return {
    item_name: String(item?.item_name ?? "").trim(),
    quantity,
    unit_price: unitPrice,
    total_price: totalPrice,
    category,
  };
};

const withRecalculatedTotal = (item) => {
  const quantity = Math.max(Number(item.quantity) || 0, 0);
  const unitPrice = Math.max(Number(item.unit_price) || 0, 0);
  return {
    ...item,
    total_price: Math.round(quantity * unitPrice * 100) / 100,
  };
};
const LOADING_MESSAGES = [
  "Reading your bill...",
  "Extracting line items...",
  "Reviewing line items...",
  "Preparing your report...",
];
const PRESCRIPTION_LOADING_MESSAGES = [
  "Reading your prescription...",
  "Extracting medicines and tests...",
  "Checking against treatment guidelines...",
  "Preparing your report...",
];
const CLINICAL_LOADING_MESSAGES = [
  "Reading your clinical documents...",
  "Reviewing symptoms and test results...",
  "Checking diagnosis support against guidelines...",
  "Preparing your report...",
];
const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.35 },
};

const HOW_IT_WORKS_STEPS = [
  {
    id: "upload",
    step: "Step 1",
    title: "Upload your bill",
    desc: "Take a photo or upload a PDF of your hospital bill.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
        <path d="M12 16V4m0 0 4 4m-4-4-4 4" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "extract",
    step: "Step 2",
    title: "OCR reads every line",
    desc: "BillCheck extracts room charges, medicines, tests, and other billed items.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <path d="M7 9h6M7 13h10M7 17h8" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "compare",
    step: "Step 3",
    title: "See what's fair",
    desc: "Each item is reviewed for suspicious charges and medicine price references where available.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
        <path d="M4 19V5M4 19h16M8 15l3-3 3 2 4-5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
];

const TRUST_BADGES = [
  { id: "free", label: "Free forever" },
  { id: "save", label: "Sign in to save bills" },
  { id: "fast", label: "Results in seconds" },
];

const TRUST_STATS = [
  { value: "Pan-India", label: "Used by patients nationwide" },
  { value: "Smart OCR", label: "Reads every line item" },
  { value: "Secure", label: "Account storage for your bills" },
];

function LandingPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const startChecking = () => {
    navigate(user ? "/check" : "/login", {
      state: user ? undefined : { from: { pathname: "/check" } },
    });
  };

  return (
    <motion.div className="landing-page" {...pageTransition}>
      <header className="landing-navbar">
        <Link to="/" className="landing-brand">
          BillCheck
        </Link>
        <UserNav className="landing-user-nav" />
      </header>

      <main className="landing-wrap">
        <section className="landing-hero">
          <motion.div
            className="hero-panel"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <p className="hero-kicker">Trusted by Indian patients</p>

            <div className="hero-content">
              <h1>Your hospital bill, clearly explained.</h1>
              <p className="hero-lead">
                BillCheck reads every line of your hospital bill and highlights
                charges that may need verification — before you pay.
              </p>
            </div>

            <div className="hero-actions">
              <button
                type="button"
                className="cta-button cta-button--hero"
                onClick={startChecking}
              >
                Check My Documents
              </button>
            </div>

            <ul className="hero-trust-badges">
              {TRUST_BADGES.map((badge, index) => (
                <motion.li
                  key={badge.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, delay: 0.45 + index * 0.1 }}
                  whileHover={{ y: -3, scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                >
                  <span className="trust-badge-dot" aria-hidden="true" />
                  {badge.label}
                </motion.li>
              ))}
            </ul>
          </motion.div>

          <motion.div
            className="phone-shell-wrap"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.12 }}
          >
            <div className="floating-panel" aria-hidden="true">
              <p>Bill Analysis</p>
              <div className="mini-bars">
                <span className="bar blue h-1" />
                <span className="bar red h-2" />
                <span className="bar blue h-3" />
                <span className="bar red h-4" />
                <span className="bar blue h-5" />
              </div>
            </div>

            <div className="android-shell">
              <div className="android-inner">
                <div className="android-status-bar" aria-hidden="true">
                  <span className="android-punch-hole" />
                </div>
                <div className="android-screen">
                  <div className="phone-top">
                    <strong>BillCheck</strong>
                    <span className="phone-dot" />
                  </div>

                  <div className="phone-summary">
                    <p>Overcharged by</p>
                    <h4>₹19,690</h4>
                  </div>

                  <div className="phone-card over">
                    <div className="phone-card-head">
                      <strong>Room Rent</strong>
                      <span className="mini-pill red">Overpriced</span>
                    </div>
                    <small>₹12,500 charged vs expected</small>
                  </div>

                  <div className="phone-card ok">
                    <div className="phone-card-head">
                      <strong>CBC Test</strong>
                      <span className="mini-pill green">Acceptable</span>
                    </div>
                    <small>₹600 charged vs expected</small>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </section>

        <section className="how-it-works">
          <div className="section-heading">
            <p className="section-eyebrow">Simple process</p>
            <h2>How BillCheck works</h2>
            <p className="section-lead">
              Three steps from upload to a clear, item-by-item fairness report.
            </p>
          </div>
          <div className="how-grid">
            {HOW_IT_WORKS_STEPS.map((item) => (
              <motion.article
                key={item.id}
                className="how-card"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.35 }}
                transition={{ duration: 0.4 }}
              >
                <div className="how-icon-wrap">{item.icon}</div>
                <p className="how-step-label">{item.step}</p>
                <h3>{item.title}</h3>
                <p>{item.desc}</p>
              </motion.article>
            ))}
          </div>
        </section>

        <section className="trust-section" aria-label="Coverage and trust">
          <ul className="trust-stats">
            {TRUST_STATS.map((stat) => (
              <li key={stat.label} className="trust-stat">
                <strong>{stat.value}</strong>
                <span>{stat.label}</span>
              </li>
            ))}
          </ul>
        </section>
      </main>

      <footer className="site-footer">
        <div className="footer-top">
          <div className="footer-brand">
            <strong>BillCheck</strong>
            <p className="footer-tagline">Know before you pay.</p>
          </div>
          <p className="footer-disclaimer">
            For informational purposes only. Review results may require manual
            verification. Actual hospital pricing may vary.
          </p>
        </div>
        <div className="footer-bottom">© {new Date().getFullYear()} BillCheck</div>
      </footer>
    </motion.div>
  );
}

function ProtectedRoute({ children }) {
  const {
    user,
    loading,
    needsEmailVerification: pendingVerification,
    termsAccepted,
    termsLoading,
  } = useAuth();
  const location = useLocation();

  if (loading || termsLoading) {
    return (
      <div className="auth-loading">
        <div className="spinner-conic" aria-hidden="true" />
        <p>Loading your account...</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (pendingVerification) {
    return (
      <Navigate
        to="/verify-email"
        replace
        state={{ from: location }}
      />
    );
  }

  if (!termsAccepted) {
    return (
      <div className="auth-loading">
        <div className="spinner-conic" aria-hidden="true" />
        <p>Loading your account...</p>
      </div>
    );
  }

  return children;
}

function TermsGate({ children }) {
  const {
    user,
    loading,
    needsEmailVerification: pendingVerification,
    termsAccepted,
    termsLoading,
    acceptTerms,
    logOut,
  } = useAuth();
  const [isAccepting, setIsAccepting] = useState(false);
  const [acceptError, setAcceptError] = useState("");

  const showTerms =
    user &&
    !pendingVerification &&
    !loading &&
    !termsLoading &&
    termsAccepted === false;

  const handleAccept = async () => {
    setAcceptError("");
    setIsAccepting(true);
    try {
      await acceptTerms();
    } catch (err) {
      setAcceptError(
        err?.message ||
          "Could not save your acceptance. Check your connection and try again."
      );
    } finally {
      setIsAccepting(false);
    }
  };

  const handleDecline = async () => {
    setAcceptError("");
    try {
      await logOut();
    } catch (err) {
      setAcceptError(err?.message || "Could not sign out. Please try again.");
    }
  };

  return (
    <>
      {children}
      {showTerms && (
        <TermsAndConditionsModal
          onAccept={handleAccept}
          onDecline={handleDecline}
          isSubmitting={isAccepting}
          error={acceptError}
        />
      )}
    </>
  );
}

function MedicalHistoryConsentGate({ children }) {
  const {
    user,
    loading,
    needsEmailVerification: pendingVerification,
    termsAccepted,
    termsLoading,
    medicalHistoryConsentResolved,
    medicalHistoryConsentLoading,
    acceptMedicalHistoryConsent,
    declineMedicalHistoryConsent,
  } = useAuth();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  const showConsent =
    user &&
    !pendingVerification &&
    !loading &&
    termsAccepted &&
    !termsLoading &&
    !medicalHistoryConsentLoading &&
    medicalHistoryConsentResolved === false;

  const handleAccept = async () => {
    setSubmitError("");
    setIsSubmitting(true);
    try {
      await acceptMedicalHistoryConsent();
    } catch (err) {
      setSubmitError(
        err?.message ||
          "Could not save your consent. Check your connection and try again."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDecline = async () => {
    setSubmitError("");
    setIsSubmitting(true);
    try {
      await declineMedicalHistoryConsent();
    } catch (err) {
      setSubmitError(err?.message || "Could not save your preference.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      {children}
      {showConsent && (
        <MedicalHistoryConsentModal
          onAccept={handleAccept}
          onDecline={handleDecline}
          isSubmitting={isSubmitting}
          error={submitError}
        />
      )}
    </>
  );
}

function CheckPage() {
  const {
    user,
    medicalHistoryConsentAccepted,
    medicalHistoryConsentLoading,
  } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const compareLocationRef = useRef({ state: "", city: "" });
  const bundleSessionRef = useRef(createBundleSession());
  const bundleSourceDocumentsRef = useRef([]);
  const [bundleDocuments, setBundleDocuments] = useState([]);
  const [pendingBundleMerge, setPendingBundleMerge] = useState(null);
  const [datePromptItems, setDatePromptItems] = useState(null);
  const [preauthDocuments, setPreauthDocuments] = useState([]);
  const [hospitalType, setHospitalType] = useState("general");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [scanMeta, setScanMeta] = useState(null);
  const [editableItems, setEditableItems] = useState([]);
  const [hospitalNameEdit, setHospitalNameEdit] = useState("");
  const [isComparing, setIsComparing] = useState(false);
  const [compareFailed, setCompareFailed] = useState(false);
  const lastCompareRef = useRef(null);
  const [loadingMessageIndex, setLoadingMessageIndex] = useState(0);
  const [loadingProgress, setLoadingProgress] = useState(8);
  const [saveMessage, setSaveMessage] = useState("");
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [hospitals, setHospitals] = useState([]);
  const [selectedHospitalId, setSelectedHospitalId] = useState("");
  const [hospitalsLoading, setHospitalsLoading] = useState(false);
  const [patientsLoading, setPatientsLoading] = useState(false);
  const [billStep, setBillStep] = useState("patient");
  const [patientInfo, setPatientInfo] = useState("");
  const [prescriptionMeta, setPrescriptionMeta] = useState(null);
  const [prescriptionMedicines, setPrescriptionMedicines] = useState([]);
  const [prescriptionTests, setPrescriptionTests] = useState([]);
  const [prescriptionProcedures, setPrescriptionProcedures] = useState([]);
  const [diagnosis, setDiagnosis] = useState("");
  const [diagnosisUserProvided, setDiagnosisUserProvided] = useState(false);
  const [clinicalStep, setClinicalStep] = useState(null);
  const [clinicalContext, setClinicalContext] = useState(emptyClinicalContext);
  const [extractionReviewActive, setExtractionReviewActive] = useState(false);
  const [extractionWarnings, setExtractionWarnings] = useState([]);

  const reloadPatients = useCallback(async () => {
    if (!user) {
      return [];
    }
    const list = await getPatients(user.uid);
    setPatients(list);
    return list;
  }, [user]);

  useEffect(() => {
    const preselected = location.state?.patientId;
    if (preselected) {
      setSelectedPatientId(preselected);
    }
  }, [location.state?.patientId]);

  useEffect(() => {
    if (selectedPatientId && patients.some((p) => p.id === selectedPatientId)) {
      if (location.state?.patientId === selectedPatientId) {
        setBillStep(location.state?.hospitalId ? "bill" : "hospital");
        if (location.state?.hospitalId) {
          setSelectedHospitalId(location.state.hospitalId);
        }
      }
    }
  }, [selectedPatientId, patients, location.state?.patientId, location.state?.hospitalId]);

  useEffect(() => {
    if (!user) {
      setPatients([]);
      return undefined;
    }
    let cancelled = false;
    const loadPatients = async () => {
      const localSnapshot = getPatientsLocalSnapshot(user.uid);
      if (!cancelled && localSnapshot.length) {
        setPatients(localSnapshot);
        setPatientsLoading(false);
      } else if (!cancelled) {
        setPatientsLoading(true);
      }
      setError("");
      try {
        await reloadPatients();
      } catch (err) {
        if (!cancelled) {
          setError(
            err.message ||
              "Could not load patients. Saved profiles on this device may still appear after refresh."
          );
        }
      } finally {
        if (!cancelled) {
          setPatientsLoading(false);
        }
      }
    };
    loadPatients();
    return () => {
      cancelled = true;
    };
  }, [user, reloadPatients]);

  const selectedPatient = patients.find((p) => p.id === selectedPatientId);
  const selectedHospital =
    hospitals.find((hospital) => hospital.id === selectedHospitalId) || null;

  const reloadHospitals = useCallback(async (patientId) => {
    if (!user || !patientId) {
      setHospitals([]);
      return [];
    }
    const localSnapshot = getLocalHospitalsSnapshot(user.uid, patientId);
    if (localSnapshot.length) {
      setHospitals(localSnapshot);
    }
    setHospitalsLoading(true);
    try {
      const list = await getPatientHospitals(user.uid, patientId);
      setHospitals(list);
      return list;
    } catch (err) {
      console.error("Failed to load hospitals:", err);
      return localSnapshot;
    } finally {
      setHospitalsLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (!selectedPatientId) {
      setHospitals([]);
      setSelectedHospitalId("");
      return;
    }
    reloadHospitals(selectedPatientId).then((list) => {
      setSelectedHospitalId((current) => {
        if (current && list.some((entry) => entry.id === current)) {
          return current;
        }
        if (location.state?.hospitalId && list.some((entry) => entry.id === location.state.hospitalId)) {
          return location.state.hospitalId;
        }
        return list[0]?.id || "";
      });
    });
  }, [selectedPatientId, reloadHospitals, location.state?.hospitalId]);

  const hospitalCompareLocation = resolveHospitalLocation(selectedHospital);
  const comparisonCopy = getComparisonSchemeCopy();
  const hasBillItems = editableItems.length > 0;
  const hasPrescriptionItems =
    prescriptionMedicines.length > 0 ||
    prescriptionTests.length > 0 ||
    prescriptionProcedures.length > 0;
  const showBillFlow = hasBillItems;
  const showPrescriptionFlow = !hasBillItems && hasPrescriptionItems;
  const showClinicalOnlyFlow = !hasBillItems && !hasPrescriptionItems;
  const activeLoadingMessages = showClinicalOnlyFlow
    ? CLINICAL_LOADING_MESSAGES
    : hasPrescriptionItems && !hasBillItems
    ? PRESCRIPTION_LOADING_MESSAGES
    : LOADING_MESSAGES;

  const buildBundleReportMeta = (reportKind) => ({
    report_kind: reportKind,
    session_id: bundleSessionRef.current.sessionId,
    source_documents: bundleSourceDocumentsRef.current,
    hospital_profile: selectedHospital
      ? {
          id: selectedHospital.id,
          name: selectedHospital.name,
          city: selectedHospital.city,
          state: selectedHospital.state,
        }
      : null,
  });

  const getConsentSaveMessage = (outcome) => {
    if (outcome?.reason === "consent_required") {
      return "Analysis complete. Report not saved — enable medical history in your account and for this patient to save reports.";
    }
    return null;
  };

  const resolvedAccountConsent = resolveAccountConsent(
    user?.uid,
    medicalHistoryConsentAccepted,
    { loading: medicalHistoryConsentLoading }
  );
  const historyConsentOptions = {
    accountConsentAccepted: medicalHistoryConsentAccepted,
    accountConsentLoading: medicalHistoryConsentLoading,
  };

  const applyBundleExtraction = (merged) => {
    bundleSourceDocumentsRef.current = merged.sourceDocuments || [];
    setPreauthDocuments(merged.preauthDocuments || []);
    setClinicalContext(merged.clinicalContext || emptyClinicalContext());

    if (merged.diagnosis) {
      setDiagnosis(merged.diagnosis);
      setDiagnosisUserProvided(false);
    }

    if (
      merged.medicines?.length ||
      merged.tests?.length ||
      merged.procedures?.length
    ) {
      setPrescriptionMeta(merged.prescriptionMeta);
      setPrescriptionMedicines(
        (merged.medicines || []).filter((item) => item.name)
      );
      setPrescriptionTests((merged.tests || []).filter((item) => item.name));
      setPrescriptionProcedures(
        (merged.procedures || []).filter((item) => item.name)
      );
    }

    if (merged.lineItems?.length) {
      setScanMeta(merged.scanMeta);
      setHospitalNameEdit(merged.scanMeta?.hospital?.name_from_bill ?? "");
      setEditableItems(merged.lineItems.map(normalizeLineItem));
    }
  };

  const handleSelectPatient = (patientId) => {
    setSelectedPatientId(patientId);
    setSelectedHospitalId("");
    setError("");
    setBillStep("hospital");
  };

  const handleSelectHospital = (hospitalId) => {
    setSelectedHospitalId(hospitalId);
    setError("");
    setBillStep("bill");
  };

  const handleChangePatient = () => {
    setBillStep("patient");
    setSelectedHospitalId("");
    setHospitals([]);
    setBundleDocuments([]);
    setPreauthDocuments([]);
    bundleSessionRef.current = createBundleSession();
    bundleSourceDocumentsRef.current = [];
    setError("");
    setResult(null);
    setScanMeta(null);
    setEditableItems([]);
    setPrescriptionMeta(null);
    setPrescriptionMedicines([]);
    setPrescriptionTests([]);
    setPrescriptionProcedures([]);
    setDiagnosis("");
    setDiagnosisUserProvided(false);
    setClinicalStep(null);
    setClinicalContext(emptyClinicalContext());
    compareLocationRef.current = { state: "", city: "" };
  };

  const handleChangeHospital = () => {
    setBillStep("hospital");
    setBundleDocuments([]);
    setPreauthDocuments([]);
    bundleSessionRef.current = createBundleSession();
    bundleSourceDocumentsRef.current = [];
    setError("");
    setResult(null);
    setScanMeta(null);
    setEditableItems([]);
    setPrescriptionMeta(null);
    setPrescriptionMedicines([]);
    setPrescriptionTests([]);
    setPrescriptionProcedures([]);
    setDiagnosis("");
    setDiagnosisUserProvided(false);
    setClinicalStep(null);
    setClinicalContext(emptyClinicalContext());
    compareLocationRef.current = { state: "", city: "" };
  };

  const getSelectedHospitalLocation = () =>
    resolveHospitalLocation(selectedHospital);

  const resolveCompareLocation = () => {
    const refLocation = compareLocationRef.current;
    const hospitalLocation = getSelectedHospitalLocation();
    const compareState =
      resolveCanonicalStateUtName(
        refLocation.state ||
          hospitalLocation.state ||
          scanMeta?.comparison_settings?.state_name ||
          ""
      ) || "";
    const compareCity =
      refLocation.city ||
      hospitalLocation.city ||
      scanMeta?.comparison_settings?.city ||
      "";
    return { state: compareState, city: compareCity, name: hospitalLocation.name };
  };

  const resolveReportKind = (fallback = "bill") => {
    const sources = bundleSourceDocumentsRef.current;
    if (!sources.length) {
      return fallback;
    }
    const types = new Set(sources.map((doc) => doc.type));
    if (types.size > 1 || sources.length > 1) {
      return "bundle";
    }
    const [singleType] = types;
    if (singleType === "prescription") {
      return "prescription";
    }
    if (singleType === "lab_report" || singleType === "discharge_summary") {
      return "clinical";
    }
    if (singleType === "bill") {
      return "bill";
    }
    return fallback;
  };

  const runBillComparison = async (
    validItems,
    locationOverride = null,
    metaOverride = {},
    analysisOverrides = {}
  ) => {
    const location =
      locationOverride?.state && locationOverride?.city
        ? locationOverride
        : resolveCompareLocation();

    if (!location.state || !location.city) {
      setError(
        "Please select a hospital with state/UT and city before comparing bills."
      );
      return;
    }

    compareLocationRef.current = location;
    setError("");
    setSaveMessage("");
    setCompareFailed(false);
    setIsComparing(true);
    lastCompareRef.current = { validItems, locationOverride, metaOverride };

    try {
      const clinicalHistory = await buildPatientHistoryPayload(
        user?.uid,
        selectedPatient,
        {
          accountConsent: resolvedAccountConsent,
        }
      );
      const prescriptionItems =
        analysisOverrides.prescriptionItems ?? buildPrescriptionRequestItems();
      const clinicalPayload = clinicalContextToApiPayload(
        analysisOverrides.clinicalContext ?? clinicalContext
      );
      const resolvedDiagnosis =
        analysisOverrides.diagnosis ?? (diagnosis.trim() || null);
      const resolvedDiagnosisUserProvided =
        analysisOverrides.diagnosisUserProvided ?? diagnosisUserProvided;
      const resolvedPreauthDocuments =
        analysisOverrides.preauthDocuments ?? preauthDocuments;
      const response = await fetchBackend(`${getApiBase()}/compare-bill`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        timeoutMs: LONG_FETCH_TIMEOUT_MS,
        body: JSON.stringify({
          line_items: validItems,
          state_ut_name: location.state,
          city: location.city,
          hospital_type: hospitalType,
          hospital_name:
            (metaOverride.hospitalName ?? hospitalNameEdit).trim() ||
            location.name ||
            selectedHospital?.name ||
            null,
          filename: metaOverride.filename ?? scanMeta?.filename,
          file_type: metaOverride.file_type ?? scanMeta?.file_type,
          bill_date: scanMeta?.bill_date || null,
          patient_district: location.city || null,
          patient_id: selectedPatient?.id || null,
          patient_name: selectedPatient?.name || null,
          ...patientAgeApiPayload(selectedPatient),
          patient_gender: selectedPatient?.gender || null,
          diagnosis: resolvedDiagnosis,
          diagnosis_user_provided: resolvedDiagnosisUserProvided,
          prescription_medicines: prescriptionItems.medicines,
          prescription_tests: prescriptionItems.tests,
          prescription_procedures: prescriptionItems.procedures,
          ...clinicalPayload,
          clinical_history: clinicalHistory,
          preauth_documents: resolvedPreauthDocuments,
          ocr_text:
            [
              metaOverride.ocr_text,
              scanMeta?.ocr_text,
              prescriptionMeta?.ocr_text,
            ]
              .filter(Boolean)
              .join("\n") || null,
        }),
      });
      const payload = await parseJsonResponse(response);
      const reportKind = resolveReportKind("bill");
      const payloadWithMeta = {
        ...payload,
        ...buildBundleReportMeta(reportKind),
      };
      setResult(payloadWithMeta);

      if (user && selectedPatient) {
        const outcome = await saveReportToAccount(
          user.uid,
          selectedPatient,
          payloadWithMeta,
          historyConsentOptions
        );
        if (outcome.saved) {
          setResult((prev) => mergeSavedReportIds(prev, outcome));
          setSaveMessage(
            outcome.localOnly
              ? "Comparison saved on this device. It will sync when you're back online."
              : "Report saved to your account."
          );
        } else {
          const consentMessage = getConsentSaveMessage(outcome);
          if (consentMessage) {
            setSaveMessage(consentMessage);
          }
        }
      }
    } catch (err) {
      setCompareFailed(true);
      setError(formatFetchError(err, "Something went wrong during comparison."));
    } finally {
      setIsComparing(false);
    }
  };

  const retryLastComparison = () => {
    const last = lastCompareRef.current;
    if (!last?.validItems?.length) {
      setError("Nothing to retry. Edit bill items and compare again.");
      return;
    }
    runBillComparison(last.validItems, last.locationOverride, last.metaOverride);
  };

  useEffect(() => {
    if (!isLoading && !isComparing) {
      setLoadingMessageIndex(0);
      setLoadingProgress(8);
      return undefined;
    }
    const messageTimer = isLoading
      ? window.setInterval(() => {
          setLoadingMessageIndex(
            (prev) => (prev + 1) % activeLoadingMessages.length
          );
        }, 2000)
      : undefined;
    const progressTimer = window.setInterval(() => {
      setLoadingProgress((prev) => Math.min(prev + 3.5, 92));
    }, 260);
    return () => {
      if (messageTimer) {
        window.clearInterval(messageTimer);
      }
      window.clearInterval(progressTimer);
    };
  }, [isLoading, isComparing, activeLoadingMessages.length]);

  const hasReportResults = Boolean(resolveResultsView(result));
  const resultsView = resolveResultsView(result);

  const uiState = isLoading
    ? "loading"
    : isComparing
    ? "comparing"
    : extractionReviewActive
    ? "extract-review"
    : clinicalStep === "diagnosis"
    ? "diagnosis"
    : clinicalStep === "clinical"
    ? "clinical"
    : hasReportResults
    ? "results"
    : editableItems.length ||
      ((prescriptionMedicines.length ||
        prescriptionTests.length ||
        prescriptionProcedures.length) &&
        !clinicalStep)
    ? "edit"
    : "upload";

  const getValidBillItemsFromMerged = (merged) =>
    (merged.lineItems || [])
      .map(normalizeLineItem)
      .filter((item) => item.item_name.trim());

  const mergedHasPrescriptionItems = (merged) =>
    Boolean(
      merged.medicines?.length ||
        merged.tests?.length ||
        merged.procedures?.length
    );

  const mergedHasClinicalOnlyData = (merged) => {
    if (mergedHasPrescriptionItems(merged)) {
      return false;
    }
    if (String(merged.diagnosis || "").trim()) {
      return true;
    }
    const clinicalContext = merged.clinicalContext || emptyClinicalContext();
    return hasClinicalData(clinicalContext);
  };

  const buildAnalysisOverridesFromMerged = (merged) => ({
    prescriptionItems: {
      medicines: merged.medicines || [],
      tests: merged.tests || [],
      procedures: merged.procedures || [],
    },
    clinicalContext: merged.clinicalContext || emptyClinicalContext(),
    diagnosis: String(merged.diagnosis || diagnosis || "").trim(),
    diagnosisUserProvided: false,
    preauthDocuments: merged.preauthDocuments || [],
  });

  const startAnalysisFromMerged = async (merged) => {
    const billItems = getValidBillItemsFromMerged(merged);
    const hasRx = mergedHasPrescriptionItems(merged);
    const overrides = buildAnalysisOverridesFromMerged(merged);
    const resolvedDiagnosis = overrides.diagnosis;

    if (merged.diagnosis && !diagnosis.trim()) {
      setDiagnosis(merged.diagnosis);
      setDiagnosisUserProvided(false);
    }

    if (billItems.length) {
      if (hasRx && !resolvedDiagnosis) {
        setClinicalStep("diagnosis");
        return;
      }
      await runBillComparison(billItems, null, {}, overrides);
      return;
    }

    if (hasRx || merged.hasClinicalDocs || mergedHasClinicalOnlyData(merged)) {
      if (!resolvedDiagnosis) {
        setClinicalStep("diagnosis");
        return;
      }
      await runPrescriptionAnalysis(resolvedDiagnosis, false, {
        medicines: merged.medicines || [],
        tests: merged.tests || [],
        procedures: merged.procedures || [],
        meta: merged.prescriptionMeta,
        clinicalContext: merged.clinicalContext,
      });
    }
  };

  const proceedAfterBundleExtraction = (
    merged,
    datedDocuments,
    { autoAnalyze = false } = {}
  ) => {
    applyBundleExtraction(merged);
    if (datedDocuments) {
      setBundleDocuments(datedDocuments);
    }

    if (!bundleHasExtractedData(merged)) {
      setError(
        "No bill items, prescription items, or clinical data were detected. Check your documents and try again."
      );
      setExtractionReviewActive(true);
      return;
    }

    const infoMessage = buildBundleExtractionInfo(merged);
    if (infoMessage) {
      setPatientInfo(infoMessage);
    }

    const needsClinical =
      merged.medicines?.length > 0 ||
      merged.tests?.length > 0 ||
      merged.procedures?.length > 0 ||
      merged.hasClinicalDocs ||
      String(merged.diagnosis || "").trim() ||
      merged.clinicalContext?.symptoms?.length > 0 ||
      merged.clinicalContext?.test_results?.length > 0;

    setClinicalStep(needsClinical ? "clinical" : null);

    if (!needsClinical && autoAnalyze) {
      void startAnalysisFromMerged(merged);
    }
  };

  const finishBundleAfterDates = (
    merged,
    datedDocuments,
    { autoAnalyze = false } = {}
  ) => {
    setExtractionReviewActive(false);
    proceedAfterBundleExtraction(merged, datedDocuments, { autoAnalyze });
  };

  const handleBundleDateConfirm = (confirmedDates) => {
    if (!pendingBundleMerge) {
      return;
    }
    const merged = mergeConfirmedDatesIntoBundle(
      pendingBundleMerge,
      bundleDocuments,
      confirmedDates
    );
    setPendingBundleMerge(null);
    setDatePromptItems(null);
    finishBundleAfterDates(merged, merged.datedDocuments);
  };

  const handleBundleDateCancel = () => {
    setPendingBundleMerge(null);
    setDatePromptItems(null);
    setExtractionReviewActive(true);
    setIsLoading(false);
  };

  const handleExtractionReviewContinue = () => {
    const docsWithData = bundleDocuments.filter((doc) => doc.editableExtraction);
    if (!docsWithData.length) {
      setError("No extracted data to continue with. Check your documents and try again.");
      return;
    }

    setError("");
    const merged = mergeEditedExtractionsToBundle(docsWithData, {
      state: hospitalCompareLocation.state,
      city: hospitalCompareLocation.city,
      hospitalType,
    });

    const promptItems = (merged.perDocumentDates || []).map((item) => ({
      ...item,
      documentDate: item.detectedDate || item.documentDate || "",
    }));

    if (itemsMissingDates(promptItems).length) {
      setPendingBundleMerge(merged);
      setDatePromptItems(promptItems);
      setExtractionReviewActive(false);
      return;
    }

    const datedMerge = mergeConfirmedDatesIntoBundle(
      merged,
      bundleDocuments,
      promptItems
    );
    finishBundleAfterDates(datedMerge, datedMerge.datedDocuments, {
      autoAnalyze: true,
    });
  };

  const handleExtractionReviewBack = () => {
    setExtractionReviewActive(false);
    setExtractionWarnings([]);
    setBundleDocuments((documents) =>
      documents.map((doc) => {
        // Strip transient extraction fields before returning to upload state.
        // eslint-disable-next-line no-unused-vars
        const { editableExtraction, rawExtraction, extractionError, ...rest } = doc;
        return rest;
      })
    );
    setError("");
    setPatientInfo("");
  };

  const handleAnalyzeBundle = async () => {
    if (!selectedPatient) {
      setError("Save a patient profile before uploading documents.");
      setBillStep("patient");
      return;
    }
    if (!selectedHospital) {
      setError("Add a hospital for this patient before uploading documents.");
      setBillStep("hospital");
      return;
    }
    if (!bundleDocuments.length) {
      setError("Add at least one document to analyze.");
      return;
    }
    if (!allBundleDocumentsConfirmed(bundleDocuments)) {
      setError(formatUnconfirmedDocumentsMessage(bundleDocuments));
      return;
    }
    if (
      bundleHasBills(bundleDocuments) &&
      (!hospitalCompareLocation.state || !hospitalCompareLocation.city)
    ) {
      setError(
        "The selected hospital must have a state/UT and city before analyzing bills."
      );
      return;
    }

    setError("");
    setPatientInfo("");
    setIsLoading(true);
    setResult(null);
    setScanMeta(null);
    setEditableItems([]);
    setPrescriptionMeta(null);
    setPrescriptionMedicines([]);
    setPrescriptionTests([]);
    setPrescriptionProcedures([]);
    setDiagnosis("");
    setDiagnosisUserProvided(false);
    setClinicalStep(null);
    setClinicalContext(emptyClinicalContext());

    try {
      const merged = await processDocumentBundle(bundleDocuments, {
        state: hospitalCompareLocation.state,
        city: hospitalCompareLocation.city,
        hospitalType,
      });
      setLoadingProgress(100);

      const docsWithExtraction = attachExtractionsToDocuments(
        bundleDocuments,
        merged.extractionByDocId || {}
      ).map((doc) => ({
        ...doc,
        extractionError: merged.extractionErrorsByDocId?.[doc.id] || null,
      }));

      setBundleDocuments(docsWithExtraction);
      setExtractionWarnings(merged.extractionWarnings || []);
      setExtractionReviewActive(true);
    } catch (err) {
      setError(formatFetchError(err, "Something went wrong during extraction."));
    } finally {
      setTimeout(() => setIsLoading(false), 250);
    }
  };

  const buildPrescriptionRequestItems = () => ({
    medicines: prescriptionMedicines.filter((item) => item.name?.trim()),
    tests: prescriptionTests.filter((item) => item.name?.trim()),
    procedures: prescriptionProcedures.filter((item) => item.name?.trim()),
  });

  const savePrescriptionReport = async (payload) => {
    if (!user || !selectedPatient) {
      return;
    }
    const reportKind = resolveReportKind("prescription");
    const reportPayload = {
      ...payload,
      report_kind: payload.report_kind || reportKind,
      ...buildBundleReportMeta(reportKind),
    };
    const outcome = await saveReportToAccount(
      user.uid,
      selectedPatient,
      reportPayload,
      historyConsentOptions
    );
    if (outcome.saved) {
      setResult((prev) => mergeSavedReportIds(prev, outcome));
      setSaveMessage(
        outcome.localOnly
          ? "Report saved on this device. Cloud sync will retry when online."
          : "Report saved to your account."
      );
    } else {
      const consentMessage = getConsentSaveMessage(outcome);
      if (consentMessage) {
        setSaveMessage(consentMessage);
      }
    }
    return outcome;
  };

  const resetToUpload = () => {
    setResult(null);
    setScanMeta(null);
    setEditableItems([]);
    setHospitalNameEdit("");
    setBundleDocuments([]);
    setPreauthDocuments([]);
    bundleSessionRef.current = createBundleSession();
    bundleSourceDocumentsRef.current = [];
    setPrescriptionMeta(null);
    setPrescriptionMedicines([]);
    setPrescriptionTests([]);
    setPrescriptionProcedures([]);
    setDiagnosis("");
    setDiagnosisUserProvided(false);
    setClinicalStep(null);
    setClinicalContext(emptyClinicalContext());
    setExtractionReviewActive(false);
    setExtractionWarnings([]);
    setPendingBundleMerge(null);
    setDatePromptItems(null);
    compareLocationRef.current = { state: "", city: "" };
    setError("");
  };

  const handleClinicalContinue = () => {
    setError("");
    if (hasPrescriptionItems && !diagnosis.trim()) {
      setClinicalStep("diagnosis");
      return;
    }
    setClinicalStep(null);
    if (showPrescriptionFlow) {
      void runPrescriptionAnalysis(diagnosis.trim(), diagnosisUserProvided);
      return;
    }
    if (hasBillItems) {
      const validItems = editableItems
        .map(normalizeLineItem)
        .filter((item) => item.item_name.trim());
      if (!validItems.length) {
        setError("Add at least one line item with a name.");
        return;
      }
      void runBillComparison(validItems);
      return;
    }
    const resolvedDiagnosis = diagnosis.trim();
    if (resolvedDiagnosis) {
      void runPrescriptionAnalysis(resolvedDiagnosis, diagnosisUserProvided);
    } else {
      setClinicalStep("diagnosis");
    }
  };

  const handleClinicalBack = () => {
    setClinicalStep(null);
    setClinicalContext(emptyClinicalContext());
    setPrescriptionMeta(null);
    setPrescriptionMedicines([]);
    setPrescriptionTests([]);
    setPrescriptionProcedures([]);
    setEditableItems([]);
    setScanMeta(null);
    setDiagnosis("");
    setDiagnosisUserProvided(false);
    setError("");
    if (bundleDocuments.some((doc) => doc.editableExtraction)) {
      setExtractionReviewActive(true);
    }
  };

  const updateLineItem = (index, field, value) => {
    setEditableItems((prev) =>
      prev.map((item, itemIndex) => {
        if (itemIndex !== index) {
          return item;
        }
        const next = { ...item, [field]: value };
        if (field === "quantity" || field === "unit_price") {
          return withRecalculatedTotal(next);
        }
        return next;
      })
    );
  };

  const removeLineItem = (index) => {
    setEditableItems((prev) => prev.filter((_, itemIndex) => itemIndex !== index));
  };

  const addLineItem = () => {
    setEditableItems((prev) => [...prev, createEmptyLineItem()]);
  };

  const handleCompare = async () => {
    const validItems = editableItems
      .map(normalizeLineItem)
      .filter((item) => item.item_name.trim());

    if (hasPrescriptionItems && !diagnosis.trim()) {
      setClinicalStep("diagnosis");
      setError("Enter a diagnosis before comparing bill and prescription.");
      return;
    }

    if (!validItems.length) {
      setError("Add at least one line item with a name.");
      return;
    }

    await runBillComparison(validItems);
  };

  const runPrescriptionAnalysis = async (
    resolvedDiagnosis,
    userProvided,
    overrides = {}
  ) => {
    const diagnosisProvided = String(resolvedDiagnosis || "").trim();
    if (!diagnosisProvided) {
      setError("Enter a diagnosis before running this check.");
      return;
    }

    const items = {
      medicines:
        overrides.medicines ??
        buildPrescriptionRequestItems().medicines,
      tests: overrides.tests ?? buildPrescriptionRequestItems().tests,
      procedures:
        overrides.procedures ?? buildPrescriptionRequestItems().procedures,
    };
    const hasTreatmentItems =
      items.medicines.length > 0 ||
      items.tests.length > 0 ||
      items.procedures.length > 0;
    const ctx = overrides.clinicalContext ?? clinicalContext;
    const clinicalOnly = !hasTreatmentItems;

    setError("");
    setIsComparing(true);
    setResult(null);
    const meta = overrides.meta ?? prescriptionMeta;
    const clinicalPayload = clinicalContextToApiPayload(ctx);
    try {
      const clinicalHistory = await buildPatientHistoryPayload(
        user?.uid,
        selectedPatient,
        {
          accountConsent: resolvedAccountConsent,
        }
      );
      const payload = await analyzeTreatment({
        diagnosis: diagnosisProvided,
        diagnosisUserProvided: userProvided,
        ...items,
        symptoms: clinicalPayload.symptoms,
        testResults: clinicalPayload.test_results,
        patient: selectedPatient,
        ocrText: meta?.ocr_text || "",
        clinicalHistory,
      });
      const reportKind = clinicalOnly
        ? resolveReportKind("clinical")
        : resolveReportKind("prescription");
      const report = {
        ...payload,
        diagnosis: diagnosisProvided,
        diagnosis_user_provided: userProvided,
        prescription: {
          diagnosis: diagnosisProvided,
          diagnosis_user_provided: userProvided,
          prescriber: meta?.prescriber || null,
          prescription_date: meta?.prescriptionDate || null,
          medicines: items.medicines,
          tests: items.tests,
          procedures: items.procedures,
        },
        clinical_context: payload.clinical_context || ctx,
        filename: meta?.filename || (clinicalOnly ? "clinical" : "prescription"),
        file_type: meta?.file_type || "manual",
        report_kind: reportKind,
        ...buildBundleReportMeta(reportKind),
      };
      setResult(report);
      const saveOutcome = await savePrescriptionReport(report);
      if (saveOutcome?.saved) {
        setResult((prev) => mergeSavedReportIds(prev, saveOutcome));
      }
    } catch (err) {
      setError(
        formatFetchError(
          err,
          clinicalOnly
            ? "Unable to run the clinical check."
            : "Unable to analyze this prescription."
        )
      );
      // Clinical-only flows have no edit page to fall back to, so without a
      // result the UI would bounce to the documents page. Return to the
      // clinical step instead: the error is visible there and the continue
      // button acts as a retry.
      if (clinicalOnly && !editableItems.length) {
        setClinicalStep("clinical");
      }
    } finally {
      setIsComparing(false);
    }
  };

  const handleDiagnosisSubmit = (value) => {
    setDiagnosis(value);
    setDiagnosisUserProvided(true);
    setClinicalStep(null);
    setError("");
    if (hasBillItems) {
      const validItems = editableItems
        .map(normalizeLineItem)
        .filter((item) => item.item_name.trim());
      if (validItems.length) {
        void runBillComparison(validItems);
        return;
      }
    }
    void runPrescriptionAnalysis(value.trim(), true);
  };

  return (
    <motion.div className="check-page" {...pageTransition}>
      <main className="check-wrap">
        <div className="check-topbar">
          <BackLink fallback="/" />
          <UserNav />
        </div>

        <header className="check-header">
          <h1>
            {uiState === "extract-review"
              ? "Review extracted data"
              : uiState === "results"
              ? "Your report"
              : billStep === "patient"
              ? "Select patient"
              : billStep === "hospital"
              ? "Select hospital"
              : uiState === "loading"
              ? "Reading your documents"
              : uiState === "comparing"
              ? "Generating your report"
              : uiState === "edit"
              ? "Review before analysis"
              : "Upload your documents"}
          </h1>
          <p>
            {uiState === "extract-review"
              ? selectedPatient && selectedHospital
                ? `Check what we read from ${selectedPatient.name}'s documents at ${selectedHospital.name}.`
                : "Check what we read from each document before continuing."
              : uiState === "results"
              ? "Review the findings below. You can download or share the full report."
              : billStep === "patient"
              ? "Choose who these documents are for."
              : billStep === "hospital"
              ? selectedPatient
                ? `Choose the hospital for ${selectedPatient.name}.`
                : "Choose the hospital for these documents."
              : uiState === "loading"
              ? selectedPatient && selectedHospital
                ? `Extracting data for ${selectedPatient.name} at ${selectedHospital.name}. This can take a minute on first use.`
                : "Extracting data from your documents. This can take a minute on first use."
              : selectedPatient && selectedHospital
              ? `Add documents for ${selectedPatient.name} at ${selectedHospital.name}.`
              : selectedPatient
              ? `Add documents for ${selectedPatient.name}.`
              : "We'll analyze them in seconds."}
          </p>
        </header>

        <AnimatePresence mode="wait">
          {uiState === "upload" && billStep === "patient" && (
            <motion.section
              key="patient-step"
              className="upload-card patient-step-card"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.25 }}
            >
              <p className="comparison-settings-title">Select patient</p>

              {patientsLoading && (
                <p className="auth-info">Loading patients...</p>
              )}

              {patients.length > 0 && (
                <PatientList
                  patients={patients}
                  selectedId={selectedPatientId}
                  mode="select"
                  onSelect={handleSelectPatient}
                />
              )}

              {!patientsLoading && patients.length === 0 && (
                <>
                  <p className="auth-info">No patients yet</p>
                  <button
                    type="button"
                    className="analyze-btn patients-add-btn"
                    onClick={() =>
                      navigate("/patients", { state: { openAddForm: true } })
                    }
                  >
                    add patients
                  </button>
                </>
              )}

              {patients.length > 0 && (
                <Link to="/patients" className="patients-manage-link">
                  Manage patients
                </Link>
              )}

              {error && <p className="error-text">{error}</p>}
            </motion.section>
          )}

          {uiState === "upload" && billStep === "hospital" && (
            <motion.section
              key="hospital-step"
              className="upload-card patient-step-card"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.25 }}
            >
              {selectedPatient && (
                <div className="patient-selected-banner patient-selected-banner-compact">
                  <p>
                    Patient: <strong>{selectedPatient.name}</strong> ·{" "}
                    {formatPatientAge(selectedPatient)}
                  </p>
                  <button
                    type="button"
                    className="bill-editor-secondary patient-change-btn"
                    onClick={handleChangePatient}
                  >
                    Change patient
                  </button>
                </div>
              )}

              <p className="comparison-settings-title">Select hospital</p>

              {hospitalsLoading && (
                <p className="auth-info">Loading hospitals...</p>
              )}

              {hospitals.length > 0 && (
                <HospitalList
                  hospitals={hospitals}
                  selectedId={selectedHospitalId}
                  mode="select"
                  onSelect={handleSelectHospital}
                />
              )}

              {!hospitalsLoading && !hospitals.length && (
                <>
                  <p className="auth-info">
                    No hospitals yet for this patient. Add a hospital before
                    uploading documents.
                  </p>
                  <Link
                    to={`/patients/${selectedPatient?.id || ""}`}
                    className="analyze-btn patients-add-btn"
                  >
                    Add hospital
                  </Link>
                </>
              )}

              {hospitals.length > 0 && (
                <Link
                  to={`/patients/${selectedPatient?.id || ""}`}
                  className="patients-manage-link"
                >
                  Manage hospitals
                </Link>
              )}

              {error && <p className="error-text">{error}</p>}
            </motion.section>
          )}

          {uiState === "upload" && billStep === "bill" && (
            <motion.section
              key="upload"
              className="upload-card"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.25 }}
            >
              {selectedPatient && selectedHospital && (
                <div className="patient-selected-banner patient-selected-banner-compact">
                  <p>
                    Patient: <strong>{selectedPatient.name}</strong> ·{" "}
                    {formatPatientAge(selectedPatient)}
                  </p>
                  <p>
                    Hospital: <strong>{selectedHospital.name}</strong>
                    {selectedHospital.city ? ` · ${selectedHospital.city}` : ""}
                    {selectedHospital.state ? `, ${selectedHospital.state}` : ""}
                  </p>
                  <div className="patient-detail-actions">
                    <button
                      type="button"
                      className="bill-editor-secondary patient-change-btn"
                      onClick={handleChangeHospital}
                    >
                      Change hospital
                    </button>
                    <button
                      type="button"
                      className="bill-editor-secondary patient-change-btn"
                      onClick={handleChangePatient}
                    >
                      Change patient
                    </button>
                  </div>
                </div>
              )}

              <p className="comparison-settings-title">Upload documents</p>

              <MultiDocumentUpload
                documents={bundleDocuments}
                onChange={setBundleDocuments}
                disabled={isLoading || isComparing}
                onValidationError={(message) => {
                  if (message) {
                    setError(message);
                  } else {
                    setError("");
                  }
                }}
              />

              {bundleHasBills(bundleDocuments) &&
                (!hospitalCompareLocation.state || !hospitalCompareLocation.city) && (
                  <p className="error-text">
                    The selected hospital must include a state/UT and city before
                    analyzing bills.{" "}
                    <Link to={`/patients/${selectedPatient?.id || ""}`}>
                      Edit hospitals
                    </Link>
                  </p>
                )}

              {bundleHasBills(bundleDocuments) && (
                <div className="comparison-settings">
                  <p className="comparison-settings-title">Hospital type</p>
                  <label className="setting-field setting-field-full">
                    <span>Hospital type</span>
                    <select
                      value={hospitalType}
                      onChange={(event) => setHospitalType(event.target.value)}
                    >
                      {HOSPITAL_TYPE_OPTIONS.map((option) => (
                        <option key={option.id} value={option.id}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <p className="comparison-settings-hint nabh-hint">
                    Hospital name from your bill is matched against the NABH registry
                    when available.
                  </p>
                </div>
              )}

              {patientInfo && <p className="auth-info">{patientInfo}</p>}

              <button
                type="button"
                className="analyze-btn"
                onClick={handleAnalyzeBundle}
                disabled={
                  isLoading ||
                  isComparing ||
                  !selectedHospital ||
                  !bundleDocuments.length ||
                  !allBundleDocumentsConfirmed(bundleDocuments) ||
                  (bundleHasBills(bundleDocuments) &&
                    (!hospitalCompareLocation.state ||
                      !hospitalCompareLocation.city))
                }
              >
                {isLoading ? "Extracting documents..." : "Extract documents"}
              </button>
              {error && <p className="error-text">{error}</p>}
            </motion.section>
          )}

          {uiState === "clinical" && (
            <motion.section
              key="clinical"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.25 }}
            >
              <ClinicalContextForm
                clinicalContext={clinicalContext}
                onChange={setClinicalContext}
                onContinue={handleClinicalContinue}
                continueLabel={
                  showPrescriptionFlow
                    ? "Check treatment appropriateness"
                    : showClinicalOnlyFlow || diagnosis.trim()
                    ? "Check diagnosis support"
                    : "Continue"
                }
                onDiagnosisExtracted={(value) => {
                  if (!diagnosis.trim() && value) {
                    setDiagnosis(value);
                    setDiagnosisUserProvided(false);
                  }
                }}
                extractedDiagnosis={diagnosis}
                onBack={
                  editableItems.length || bundleDocuments.length
                    ? handleClinicalBack
                    : null
                }
                error={error}
              />
            </motion.section>
          )}

          {uiState === "diagnosis" && (
            <motion.section
              key="diagnosis"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.25 }}
            >
              <DiagnosisPrompt
                initialDiagnosis={diagnosis}
                onSubmit={handleDiagnosisSubmit}
                onCancel={() => {
                  setClinicalStep("clinical");
                  setError("");
                }}
                error={error}
              />
            </motion.section>
          )}

          {(uiState === "loading" || uiState === "comparing") && (
            <motion.section
              key={uiState === "comparing" ? "comparing" : "loading"}
              className="loading-card"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.25 }}
            >
              <div className="spinner-conic" aria-hidden="true" />
              <p className="loading-message">
                {uiState === "comparing"
                  ? showClinicalOnlyFlow
                    ? "Checking clinical evidence against guidelines..."
                    : showPrescriptionFlow
                    ? "Checking against treatment guidelines..."
                    : comparisonCopy.loading
                  : activeLoadingMessages[loadingMessageIndex]}
              </p>
              <div className="loading-bar">
                <div className="loading-bar-fill" style={{ width: `${loadingProgress}%` }} />
              </div>
            </motion.section>
          )}

          {uiState === "extract-review" && (
            <motion.section
              key="extract-review"
              className="upload-card"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.25 }}
            >
              <BundleExtractionReview
                documents={bundleDocuments}
                onChange={setBundleDocuments}
                onContinue={handleExtractionReviewContinue}
                onBack={handleExtractionReviewBack}
                disabled={isLoading || isComparing}
                error={error}
                extractionWarnings={extractionWarnings}
              />
            </motion.section>
          )}

          {uiState === "edit" && showBillFlow && editableItems.length > 0 && (
            <motion.section
              key="edit"
              className="bill-editor-shell"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.25 }}
            >
              <header className="bill-editor-header">
                <div>
                  <h2>Review scanned items</h2>
                  <p>{comparisonCopy.editHint}</p>
                </div>
                <span className="bill-editor-count">
                  {editableItems.length} item{editableItems.length === 1 ? "" : "s"}
                </span>
              </header>

              {(hasPrescriptionItems || diagnosis) && (
                <div className="prescription-review-panel">
                  <h3>Prescription summary</h3>
                  {diagnosis ? (
                    <p className="comparison-context">
                      Diagnosis: <strong>{diagnosis}</strong>
                    </p>
                  ) : (
                    <p className="comparison-settings-hint">
                      Diagnosis will be requested before comparison.
                    </p>
                  )}
                  {[...prescriptionMedicines, ...prescriptionTests, ...prescriptionProcedures]
                    .length > 0 && (
                    <ul className="prescription-inline-list">
                      {prescriptionMedicines.map((item, index) => (
                        <li key={`med-${index}`}>Medicine: {item.name}</li>
                      ))}
                      {prescriptionTests.map((item, index) => (
                        <li key={`test-${index}`}>Test: {item.name}</li>
                      ))}
                      {prescriptionProcedures.map((item, index) => (
                        <li key={`proc-${index}`}>Procedure: {item.name}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              <label className="setting-field setting-field-full bill-editor-hospital">
                <span>Hospital name (optional)</span>
                <input
                  type="text"
                  value={hospitalNameEdit}
                  placeholder="As shown on the bill"
                  onChange={(event) => setHospitalNameEdit(event.target.value)}
                />
              </label>

              <ul className="bill-editor-list">
                {editableItems.map((item, index) => (
                  <li key={`line-item-${index}`} className="bill-editor-row">
                    <div className="bill-editor-row-top">
                      <label className="bill-editor-field bill-editor-field-grow">
                        <span>Item</span>
                        <input
                          type="text"
                          value={item.item_name}
                          placeholder="e.g. CBC Test, Room rent"
                          onChange={(event) =>
                            updateLineItem(index, "item_name", event.target.value)
                          }
                        />
                      </label>
                      <button
                        type="button"
                        className="bill-editor-remove"
                        onClick={() => removeLineItem(index)}
                        aria-label={`Remove item ${index + 1}`}
                        title="Remove item"
                      >
                        ×
                      </button>
                    </div>
                    <div className="bill-editor-row-grid">
                      <label className="bill-editor-field">
                        <span>Qty</span>
                        <input
                          type="number"
                          min="0"
                          step="1"
                          value={item.quantity}
                          onChange={(event) =>
                            updateLineItem(
                              index,
                              "quantity",
                              Number(event.target.value)
                            )
                          }
                        />
                      </label>
                      <label className="bill-editor-field">
                        <span>Unit price (₹)</span>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={item.unit_price}
                          onChange={(event) =>
                            updateLineItem(
                              index,
                              "unit_price",
                              Number(event.target.value)
                            )
                          }
                        />
                      </label>
                      <label className="bill-editor-field">
                        <span>Total (₹)</span>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={item.total_price}
                          onChange={(event) =>
                            updateLineItem(
                              index,
                              "total_price",
                              Number(event.target.value)
                            )
                          }
                        />
                      </label>
                      <label className="bill-editor-field">
                        <span>Category</span>
                        <select
                          value={item.category}
                          onChange={(event) =>
                            updateLineItem(index, "category", event.target.value)
                          }
                        >
                          {CATEGORY_OPTIONS.map((option) => (
                            <option key={option.id} value={option.id}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                  </li>
                ))}
              </ul>

              <button
                type="button"
                className="bill-editor-add"
                onClick={addLineItem}
              >
                + Add line item
              </button>

              <div className="bill-editor-actions">
                <button
                  type="button"
                  className="bill-editor-secondary"
                  onClick={resetToUpload}
                >
                  Upload different documents
                </button>
                <button
                  type="button"
                  className="analyze-btn bill-editor-primary"
                  onClick={handleCompare}
                >
                  {hasPrescriptionItems
                    ? "Compare bill & check treatment"
                    : comparisonCopy.compareButton}
                </button>
              </div>
              {error && (
                <div className="compare-error-block">
                  <p className="error-text">{error}</p>
                  {compareFailed && (
                    <button
                      type="button"
                      className="bill-editor-secondary compare-retry-btn"
                      onClick={retryLastComparison}
                      disabled={isComparing}
                    >
                      Retry comparison
                    </button>
                  )}
                </div>
              )}
            </motion.section>
          )}

          {uiState === "edit" && showPrescriptionFlow && (
            <motion.section
              key="prescription-edit"
              className="bill-editor-shell"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.25 }}
            >
              <header className="bill-editor-header">
                <div>
                  <h2>Review prescription items</h2>
                  <p>
                    Confirm medicines, tests, and procedures before checking against
                    Standard Treatment Guidelines.
                  </p>
                </div>
              </header>

              {diagnosis && (
                <p className="comparison-context">
                  Diagnosis: <strong>{diagnosis}</strong>
                </p>
              )}

              <button
                type="button"
                className="bill-editor-secondary"
                onClick={() => setClinicalStep("clinical")}
              >
                Add symptoms & test results (optional)
              </button>

              <div className="prescription-editor-groups">
                {[
                  ["Medicines", prescriptionMedicines, setPrescriptionMedicines],
                  ["Tests", prescriptionTests, setPrescriptionTests],
                  ["Procedures", prescriptionProcedures, setPrescriptionProcedures],
                ].map(([label, items, setter]) => (
                  <div key={label} className="prescription-editor-group">
                    <h3>{label}</h3>
                    <ul className="bill-editor-list">
                      {items.map((item, index) => (
                        <li key={`${label}-${index}`} className="bill-editor-row">
                          <label className="bill-editor-field bill-editor-field-grow">
                            <span>Name</span>
                            <input
                              type="text"
                              value={item.name}
                              onChange={(event) => {
                                setter((prev) =>
                                  prev.map((entry, entryIndex) =>
                                    entryIndex === index
                                      ? { ...entry, name: event.target.value }
                                      : entry
                                  )
                                );
                              }}
                            />
                          </label>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>

              <div className="bill-editor-actions">
                <button
                  type="button"
                  className="bill-editor-secondary"
                  onClick={resetToUpload}
                >
                  Upload different documents
                </button>
                <button
                  type="button"
                  className="analyze-btn bill-editor-primary"
                  onClick={() => {
                    if (!diagnosis.trim()) {
                      setClinicalStep("diagnosis");
                      return;
                    }
                    runPrescriptionAnalysis(diagnosis.trim(), diagnosisUserProvided);
                  }}
                >
                  Check treatment appropriateness
                </button>
              </div>
              {error && <p className="error-text">{error}</p>}
            </motion.section>
          )}

          {uiState === "results" && resultsView === "bill" && (
            <motion.section
              key="results"
              className="results-shell"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
            >
              {saveMessage && <p className="save-message">{saveMessage}</p>}
              <BillResults
                result={result}
                onReportUpdate={setResult}
                toolbar={
                  <button
                    type="button"
                    className="bill-editor-secondary"
                    onClick={() => {
                      if (result?.line_items?.length) {
                        setEditableItems(result.line_items.map(normalizeLineItem));
                      }
                      setResult(null);
                      setSaveMessage("");
                      setError("");
                    }}
                  >
                    ← Edit bill items
                  </button>
                }
              />
            </motion.section>
          )}

          {uiState === "results" && resultsView === "prescription" && (
            <motion.section
              key="prescription-results"
              className="results-shell"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
            >
              {saveMessage && <p className="save-message">{saveMessage}</p>}
              <PrescriptionResults
                result={result}
                onReportUpdate={setResult}
                toolbar={
                  <button
                    type="button"
                    className="bill-editor-secondary"
                    onClick={() => {
                      setResult(null);
                      setSaveMessage("");
                      setError("");
                    }}
                  >
                    ←{" "}
                    {result?.report_kind === "clinical"
                      ? "Review clinical data"
                      : "Review prescription"}
                  </button>
                }
              />
            </motion.section>
          )}
        </AnimatePresence>

        {datePromptItems?.length > 0 && (
          <DocumentDatePrompt
            items={datePromptItems}
            title="When were these documents issued?"
            description="We could not read a date on some uploaded documents. Enter the date each one relates to so your medical history stays accurate."
            confirmLabel="Continue to review"
            onConfirm={handleBundleDateConfirm}
            onCancel={handleBundleDateCancel}
          />
        )}
      </main>
    </motion.div>
  );
}

function AppRoutes() {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        {import.meta.env.DEV && (
          <Route path="/__dev/terms" element={<TermsDevPreview />} />
        )}
        <Route
          path="/account"
          element={
            <ProtectedRoute>
              <AccountSettingsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/check"
          element={
            <ProtectedRoute>
              <CheckPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/patients"
          element={
            <ProtectedRoute>
              <PatientsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/patients/:patientId"
          element={
            <ProtectedRoute>
              <PatientsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/consent/medical-history"
          element={
            <ProtectedRoute>
              <MedicalHistoryConsentPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/history"
          element={
            <ProtectedRoute>
              <HistoryPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/history/:billId"
          element={
            <ProtectedRoute>
              <HistoryPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/action"
          element={
            <ProtectedRoute>
              <TakeActionPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/action/:billId"
          element={
            <ProtectedRoute>
              <TakeActionPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AndroidBackButtonHandler />
        <div className="app-shell">
          <AppBackground />
          <div className="app-content">
            <TermsGate>
              <MedicalHistoryConsentGate>
                <AppRoutes />
              </MedicalHistoryConsentGate>
            </TermsGate>
          </div>
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
}
