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
import { HOSPITAL_TYPE_OPTIONS } from "./billUtils";
import { AuthProvider, useAuth } from "./context/AuthContext";
import LoginPage from "./pages/LoginPage";
import HistoryPage from "./pages/HistoryPage";
import PatientsPage from "./pages/PatientsPage";
import AccountSettingsPage from "./pages/AccountSettingsPage";
import VerifyEmailPage from "./pages/VerifyEmailPage";
import PatientForm, { emptyPatientForm } from "./components/PatientForm";
import PatientList from "./components/PatientList";
import LocationSearchPicker from "./components/LocationSearchPicker";
import { Capacitor } from "@capacitor/core";
import { createPatient, getPatients, getPatientsLocalSnapshot } from "./services/patients";
import { markLocalBillSynced, persistLocalBill, saveBill } from "./services/bills";

// Web dev: leave unset so requests use the Vite proxy (/api → :8000).
// Set VITE_API_BASE in .env for production APK or a deployed API.
const API_BASE =
  import.meta.env.VITE_API_BASE ??
  (Capacitor.isNativePlatform() ? "http://10.0.2.2:8000" : "");
const ALLOWED_EXTENSIONS = ["pdf", "jpg", "jpeg", "png"];

function formatFetchError(err, fallback) {
  if (err?.message === "Failed to fetch") {
    return "Could not reach the backend. Start it on port 8000 and refresh.";
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
  "Comparing with CGHS rates...",
  "Preparing your report...",
];

const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.35 },
};

const isSupportedFile = (file) => {
  const ext = file.name.split(".").pop()?.toLowerCase();
  return Boolean(ext && ALLOWED_EXTENSIONS.includes(ext));
};

function UserNav({ className = "" }) {
  const { user, logOut, loading } = useAuth();

  if (loading) {
    return null;
  }

  if (!user) {
    return (
      <div className={`user-nav ${className}`.trim()}>
        <Link to="/login" className="user-nav-link">
          Sign in
        </Link>
      </div>
    );
  }

  return (
    <div className={`user-nav ${className}`.trim()}>
      <Link to="/patients" className="user-nav-link">
        Patients
      </Link>
      <Link to="/history" className="user-nav-link">
        Past bills
      </Link>
      <Link to="/account" className="user-nav-link">
        Account
      </Link>
      <span className="user-nav-email">{user.email || "Signed in"}</span>
      <button
        type="button"
        className="user-nav-signout"
        onClick={() => logOut()}
      >
        Sign out
      </button>
    </div>
  );
}

function ProtectedRoute({ children }) {
  const { user, loading, needsEmailVerification: pendingVerification } = useAuth();
  const location = useLocation();

  if (loading) {
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

  return children;
}

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
      <div className="landing-bg-blobs" aria-hidden="true">
        <span className="blob blob-blue" />
        <span className="blob blob-green" />
        <span className="blob blob-purple" />
      </div>

      <header className="landing-navbar">
        <div className="landing-brand">
          <span>BillCheck</span>
          <span className="pulse-dot" aria-hidden="true" />
        </div>
        <UserNav className="landing-user-nav" />
      </header>

      <main className="landing-wrap">
        <section className="landing-hero">
          <motion.div
            className="hero-copy"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <p className="eyebrow">Trusted by Indian patients</p>
            <h1>Your hospital bill, finally explained.</h1>
            <p>
              BillCheck reads every line of your hospital bill and compares it
              against official CGHS government rates. Know exactly what&apos;s fair
              - before you pay.
            </p>
            <button
              type="button"
              className="cta-button"
              onClick={startChecking}
            >
              Check My Bill →
            </button>
            <div className="trust-inline">
              <span>✓ Free forever</span>
              <span>•</span>
              <span>✓ Sign in to save bills</span>
              <span>•</span>
              <span>✓ Results in seconds</span>
            </div>
          </motion.div>

          <motion.div
            className="phone-shell-wrap"
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.55 }}
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

            <div className="iphone-shell">
              <div className="iphone-inner">
                <div className="dynamic-island" />
                <div className="iphone-screen">
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
                    <small>₹12,500 charged vs ₹2,500 CGHS</small>
                  </div>

                  <div className="phone-card ok">
                    <div className="phone-card-head">
                      <strong>CBC Test</strong>
                      <span className="mini-pill green">Acceptable</span>
                    </div>
                    <small>₹600 charged vs ₹350 CGHS</small>
                  </div>

                  <div className="phone-card over">
                    <div className="phone-card-head">
                      <strong>Blood Transfusion</strong>
                      <span className="mini-pill red">Overpriced</span>
                    </div>
                    <small>₹7,000 vs ₹1,800 CGHS</small>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </section>

        <section className="how-it-works">
          <h2>How BillCheck works</h2>
          <div className="how-grid">
            {[
              {
                icon: "📄",
                step: "Step 1",
                title: "Upload your bill",
                desc: "Take a photo or upload a PDF of your hospital bill",
              },
              {
                icon: "🤖",
                step: "Step 2",
                title: "Optical character recognition",
                desc: "Our system extracts every line item - medicines, tests, room charges, fees",
              },
              {
                icon: "📊",
                step: "Step 3",
                title: "See what's fair",
                desc: "Each item is compared against official CGHS government benchmark rates",
              },
            ].map((item) => (
              <motion.article
                key={item.title}
                className="how-card"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.35 }}
                transition={{ duration: 0.4 }}
              >
                <span className="how-icon">{item.icon}</span>
                <p className="how-step-label">{item.step}</p>
                <h3>{item.title}</h3>
                <p>{item.desc}</p>
              </motion.article>
            ))}
          </div>
        </section>

        <section className="trust-bar-dark">
          Comparing against 5,900+ official CGHS 2025 rates · Used by patients across
          India · Secure account storage · Built with ❤️ for India
        </section>
      </main>

      <footer className="site-footer">
        <div className="footer-top">
          <div>
            <strong>BillCheck</strong>
            <p>Know before you pay.</p>
          </div>
          <p>
            For informational purposes only. CGHS rates are government
            benchmarks. Actual hospital pricing may vary.
          </p>
        </div>
        <div className="footer-bottom">© {new Date().getFullYear()} BillCheck</div>
      </footer>
    </motion.div>
  );
}

function CheckPage() {
  const { user } = useAuth();
  const location = useLocation();
  const inputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [states, setStates] = useState([]);
  const [cities, setCities] = useState([]);
  const [stateUtName, setStateUtName] = useState("");
  const [city, setCity] = useState("");
  const [resolvedTier, setResolvedTier] = useState(null);
  const [hospitalType, setHospitalType] = useState("general");
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingCities, setIsLoadingCities] = useState(false);
  const [locationError, setLocationError] = useState("");
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [scanMeta, setScanMeta] = useState(null);
  const [editableItems, setEditableItems] = useState([]);
  const [hospitalNameEdit, setHospitalNameEdit] = useState("");
  const [isComparing, setIsComparing] = useState(false);
  const [loadingMessageIndex, setLoadingMessageIndex] = useState(0);
  const [loadingProgress, setLoadingProgress] = useState(8);
  const [saveMessage, setSaveMessage] = useState("");
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [patientsLoading, setPatientsLoading] = useState(false);
  const [billStep, setBillStep] = useState("patient");
  const [showNewPatientForm, setShowNewPatientForm] = useState(false);
  const [patientForm, setPatientForm] = useState(emptyPatientForm);
  const [patientSaving, setPatientSaving] = useState(false);
  const [patientInfo, setPatientInfo] = useState("");

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
        setBillStep("bill");
      }
    }
  }, [selectedPatientId, patients, location.state?.patientId]);

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

  const handleSaveNewPatient = async (event) => {
    event.preventDefault();
    if (!user?.uid) {
      setError("You must be signed in to save a patient.");
      return;
    }
    setPatientSaving(true);
    setError("");
    setPatientInfo("");
    try {
      const result = await createPatient(user.uid, patientForm);
      const list = await reloadPatients();
      const saved =
        list.find((p) => p.id === result.id) ||
        list.find((p) => p.localId === result.localId) ||
        result.patient;
      const patientId = saved?.id || result.id;
      setSelectedPatientId(patientId);
      setShowNewPatientForm(false);
      setPatientForm(emptyPatientForm());
      setBillStep("bill");
      setPatientInfo(
        `Patient "${saved?.name || patientForm.name}" saved. You can upload the bill now.`
      );
    } catch (err) {
      setError(err.message || "Unable to save patient.");
    } finally {
      setPatientSaving(false);
    }
  };

  const handleContinueWithPatient = () => {
    if (!selectedPatientId || !selectedPatient) {
      setError("Select or add a patient before uploading a bill.");
      return;
    }
    setError("");
    setBillStep("bill");
  };

  const handleChangePatient = () => {
    setBillStep("patient");
    setSelectedFile(null);
    setError("");
    setResult(null);
    setScanMeta(null);
    setEditableItems([]);
  };

  useEffect(() => {
    const loadStates = async () => {
      setLocationError("");
      try {
        const url = `${API_BASE}/api/locations/states`;
        const response = await fetch(url);
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload?.detail || "Unable to load states.");
        }
        setStates(Array.isArray(payload) ? payload : []);
      } catch (err) {
        setStates([]);
        setLocationError(formatFetchError(err, "Unable to load state list."));
      }
    };
    loadStates();
  }, []);

  useEffect(() => {
    if (!stateUtName) {
      setCities([]);
      setCity("");
      setResolvedTier(null);
      return undefined;
    }

    const loadCities = async () => {
      setIsLoadingCities(true);
      setLocationError("");
      setCity("");
      setResolvedTier(null);
      try {
        const response = await fetch(
          `${API_BASE}/api/locations/cities?state=${encodeURIComponent(stateUtName)}`
        );
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload?.detail || "Unable to load cities.");
        }
        setCities(Array.isArray(payload) ? payload : []);
      } catch (err) {
        setCities([]);
        setLocationError(formatFetchError(err, "Unable to load cities for this state."));
      } finally {
        setIsLoadingCities(false);
      }
    };

    loadCities();
  }, [stateUtName]);

  useEffect(() => {
    if (!stateUtName || !city) {
      setResolvedTier(null);
      return undefined;
    }

    let cancelled = false;
    const loadTier = async () => {
      try {
        const params = new URLSearchParams({
          state: stateUtName,
          city,
        });
        const response = await fetch(`${API_BASE}/api/locations/tier?${params}`);
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload?.detail || "Unable to resolve city tier.");
        }
        if (!cancelled) {
          setResolvedTier(payload);
        }
      } catch {
        if (!cancelled) {
          setResolvedTier(null);
        }
      }
    };

    loadTier();
    return () => {
      cancelled = true;
    };
  }, [stateUtName, city]);

  useEffect(() => {
    if (!isLoading && !isComparing) {
      setLoadingMessageIndex(0);
      setLoadingProgress(8);
      return undefined;
    }
    const messageTimer = isLoading
      ? window.setInterval(() => {
          setLoadingMessageIndex((prev) => (prev + 1) % LOADING_MESSAGES.length);
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
  }, [isLoading, isComparing]);

  const uiState = isLoading
    ? "loading"
    : isComparing
    ? "comparing"
    : result?.line_items?.length
    ? "results"
    : editableItems.length
    ? "edit"
    : "upload";

  const handleFileSelection = (file) => {
    if (!file) {
      return;
    }
    if (!isSupportedFile(file)) {
      setError("Please upload a valid PDF, JPG, JPEG, or PNG file.");
      setSelectedFile(null);
      return;
    }
    setError("");
    setResult(null);
    setScanMeta(null);
    setEditableItems([]);
    setHospitalNameEdit("");
    setSelectedFile(file);
  };

  const resetToUpload = () => {
    setResult(null);
    setScanMeta(null);
    setEditableItems([]);
    setHospitalNameEdit("");
    setError("");
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

    if (!validItems.length) {
      setError("Add at least one line item with a name.");
      return;
    }

    if (!stateUtName || !city) {
      setError("Location settings are missing. Please upload the bill again.");
      return;
    }

    setError("");
    setSaveMessage("");
    setIsComparing(true);

    try {
      const response = await fetch(`${API_BASE}/compare-bill`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          line_items: validItems,
          state_ut_name: stateUtName,
          city,
          hospital_type: hospitalType,
          hospital_name: hospitalNameEdit.trim() || null,
          filename: scanMeta?.filename,
          file_type: scanMeta?.file_type,
          pmjay_eligible: Boolean(selectedPatient?.ayushmanEligible),
          patient_id: selectedPatient?.id || null,
          patient_name: selectedPatient?.name || null,
          patient_age: selectedPatient?.age ?? null,
          patient_gender: selectedPatient?.gender || null,
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        const detail = payload?.detail;
        const message = Array.isArray(detail)
          ? detail.map((entry) => entry.msg).join(", ")
          : detail;
        throw new Error(message || "Unable to compare this bill.");
      }
      setResult(payload);
      setIsComparing(false);

      if (user && selectedPatient?.savePastBills) {
        const localId = persistLocalBill(user.uid, payload);
        saveBill(user.uid, payload, {
          localId,
          patientId: selectedPatient?.id || null,
        })
          .then((firestoreId) => {
            markLocalBillSynced(user.uid, localId, firestoreId);
            setSaveMessage("Bill saved to your account.");
          })
          .catch((saveErr) => {
            const offline = typeof navigator !== "undefined" && !navigator.onLine;
            setSaveMessage(
              saveErr.message ||
                (offline
                  ? "Comparison saved on this device. It will sync when you're back online."
                  : "Comparison saved on this device. Open Past bills to retry syncing to your account.")
            );
          });
      }
    } catch (err) {
      setError(err.message || "Something went wrong during comparison.");
      setIsComparing(false);
    }
  };

  const handleAnalyze = async () => {
    if (!selectedPatient) {
      setError("Save a patient profile before uploading a bill.");
      setBillStep("patient");
      return;
    }
    if (!selectedFile) {
      setError("Please select your hospital bill first.");
      return;
    }
    if (!stateUtName || !city) {
      setError("Please select the state/UT and city where the hospital is located.");
      return;
    }
    setError("");
    setIsLoading(true);
    setResult(null);
    setScanMeta(null);
    setEditableItems([]);
    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const params = new URLSearchParams({
        state_ut_name: stateUtName,
        city,
        hospital_type: hospitalType,
      });
      const response = await fetch(`${API_BASE}/upload-bill?${params}`, {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || "Unable to analyze this bill.");
      }
      setLoadingProgress(100);
      const items = (payload.line_items ?? []).map(normalizeLineItem);
      if (!items.length) {
        throw new Error("No line items were found on this bill.");
      }
      setScanMeta({
        filename: payload.filename,
        file_type: payload.file_type,
        hospital: payload.hospital,
        comparison_settings: payload.comparison_settings,
      });
      setHospitalNameEdit(payload.hospital?.name_from_bill ?? "");
      setEditableItems(items);
    } catch (err) {
      setError(err.message || "Something went wrong during analysis.");
    } finally {
      setTimeout(() => setIsLoading(false), 250);
    }
  };

  return (
    <motion.div className="check-page" {...pageTransition}>
      <main className="check-wrap">
        <div className="check-topbar">
          <Link to="/" className="back-link">
            ← Back
          </Link>
          <UserNav />
        </div>

        <header className="check-header">
          <h1>
            {billStep === "patient"
              ? "Set up patient"
              : "Upload your hospital bill"}
          </h1>
          <p>
            {billStep === "patient"
              ? "Add or select a patient before uploading a medical bill."
              : selectedPatient
              ? `Checking bill for ${selectedPatient.name}.`
              : "We'll analyze it in seconds."}
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
              <p className="comparison-settings-title">Step 1 — Patient profile</p>

              {patientsLoading && (
                <p className="auth-info">Loading patients...</p>
              )}

              {patients.length > 0 && !showNewPatientForm && (
                <PatientList
                  patients={patients}
                  selectedId={selectedPatientId}
                  mode="select"
                  onSelect={(patientId) => {
                    setSelectedPatientId(patientId);
                    setError("");
                  }}
                />
              )}

              {selectedPatient && !showNewPatientForm && (
                <div className="patient-selected-banner">
                  <p>
                    <strong>{selectedPatient.name}</strong> · {selectedPatient.age}{" "}
                    yrs · {selectedPatient.gender}
                    {selectedPatient.ayushmanEligible && " · PM-JAY eligible"}
                  </p>
                  <button
                    type="button"
                    className="analyze-btn"
                    onClick={handleContinueWithPatient}
                  >
                    Continue to upload bill →
                  </button>
                </div>
              )}

              {!showNewPatientForm && (
                <button
                  type="button"
                  className="bill-editor-add patients-add-inline"
                  onClick={() => {
                    setShowNewPatientForm(true);
                    setPatientForm(emptyPatientForm());
                    setSelectedPatientId("");
                    setError("");
                  }}
                >
                  + Add new patient
                </button>
              )}

              {!showNewPatientForm && patients.length > 0 && (
                <Link to="/patients" className="patients-manage-link">
                  Manage patients
                </Link>
              )}

              {showNewPatientForm && (
                <section className="patient-card-shell">
                  <h2>New patient</h2>
                  <PatientForm
                    form={patientForm}
                    setForm={setPatientForm}
                    onSubmit={handleSaveNewPatient}
                    onCancel={() => {
                      setShowNewPatientForm(false);
                      setPatientForm(emptyPatientForm());
                    }}
                    submitLabel="Save patient & continue"
                    saving={patientSaving}
                    error={error}
                    info={patientInfo}
                    isCreate
                  />
                </section>
              )}

              {!showNewPatientForm && patients.length === 0 && !patientsLoading && (
                <section className="patient-card-shell">
                  <h2>Add your first patient</h2>
                  <p className="comparison-settings-hint">
                    You need a saved patient profile before uploading a bill.
                  </p>
                  <PatientForm
                    form={patientForm}
                    setForm={setPatientForm}
                    onSubmit={handleSaveNewPatient}
                    submitLabel="Save patient & continue"
                    saving={patientSaving}
                    error={error}
                    info={patientInfo}
                    isCreate
                  />
                </section>
              )}

              {patientInfo && !showNewPatientForm && patients.length > 0 && (
                <p className="auth-info">{patientInfo}</p>
              )}
              {error && !showNewPatientForm && (
                <p className="error-text">{error}</p>
              )}
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
              {selectedPatient && (
                <div className="patient-selected-banner patient-selected-banner-compact">
                  <p>
                    Patient: <strong>{selectedPatient.name}</strong> ·{" "}
                    {selectedPatient.age} yrs
                    {selectedPatient.ayushmanEligible && " · PM-JAY eligible"}
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

              <p className="comparison-settings-title">Step 2 — Upload bill</p>

              <button
                type="button"
                className={`upload-zone ${isDragging ? "upload-zone-dragging" : ""}`}
                onClick={() => inputRef.current?.click()}
                onDrop={(event) => {
                  event.preventDefault();
                  setIsDragging(false);
                  handleFileSelection(event.dataTransfer.files?.[0]);
                }}
                onDragOver={(event) => {
                  event.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={(event) => {
                  event.preventDefault();
                  setIsDragging(false);
                }}
              >
                <div className="upload-icon">↑</div>
                <p className="upload-title">Drop your bill here or click to browse</p>
                <p className="upload-subtitle">Supports PDF, JPG, PNG</p>
                {selectedFile && <p className="file-name">{selectedFile.name}</p>}
              </button>
              <input
                ref={inputRef}
                className="hidden-input"
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
                onChange={(event) => {
                  handleFileSelection(event.target.files?.[0]);
                  event.target.value = "";
                }}
              />

              {selectedPatient?.ayushmanEligible && (
                <p className="comparison-settings-hint pmjay-hint">
                  Procedures and tests will be compared against Ayushman Bharat HBP
                  2022 rates (medicines use NPPA ceiling prices).
                </p>
              )}

              <div className="comparison-settings">
                <p className="comparison-settings-title">Hospital location</p>
                <div className="comparison-settings-grid">
                  <LocationSearchPicker
                    label="State/UT"
                    items={states}
                    value={stateUtName}
                    onSelect={setStateUtName}
                    disabled={!states.length && !locationError}
                    isLoading={!states.length && !locationError}
                    loadingLabel="Loading states..."
                    placeholder="Select state/UT"
                    emptyLabel={
                      locationError
                        ? "Could not load states"
                        : "No states available"
                    }
                  />
                  <LocationSearchPicker
                    label="City"
                    items={cities}
                    value={city}
                    onSelect={setCity}
                    disabled={!stateUtName}
                    isLoading={isLoadingCities}
                    loadingLabel="Loading cities..."
                    placeholder="Select city"
                    emptyLabel={
                      stateUtName
                        ? "No cities available"
                        : "Select state/UT first"
                    }
                  />
                </div>
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
                  For general hospitals, NABH vs non-NABH rates are chosen
                  automatically by matching the hospital name from your bill
                  against the official NABH registry.
                </p>
                {resolvedTier && (
                  <p className="tier-detected">
                    CGHS tier for this city:{" "}
                    <strong>{resolvedTier.tier_label}</strong>
                    {resolvedTier.tier_source === "default_tier_3"
                      ? " (not in CGHS city list — Tier III applied)"
                      : ""}
                  </p>
                )}
                <p className="comparison-settings-hint">
                  City tier is detected automatically from official CGHS city
                  classification. Unlisted cities use Tier III rates.
                </p>
                {locationError && (
                  <p className="error-text">{locationError}</p>
                )}
              </div>

              <button type="button" className="analyze-btn" onClick={handleAnalyze}>
                Analyze Bill
              </button>
              {error && <p className="error-text">{error}</p>}
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
                  ? selectedPatient?.ayushmanEligible
                    ? "Comparing with Ayushman Bharat HBP 2022 rates..."
                    : "Comparing with CGHS rates..."
                  : LOADING_MESSAGES[loadingMessageIndex]}
              </p>
              <div className="loading-bar">
                <div className="loading-bar-fill" style={{ width: `${loadingProgress}%` }} />
              </div>
            </motion.section>
          )}

          {uiState === "edit" && (
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
                  <p>
                    Correct anything the scan missed, then compare against CGHS
                    rates.
                  </p>
                </div>
                <span className="bill-editor-count">
                  {editableItems.length} item{editableItems.length === 1 ? "" : "s"}
                </span>
              </header>

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
                  Upload different bill
                </button>
                <button
                  type="button"
                  className="analyze-btn bill-editor-primary"
                  onClick={handleCompare}
                >
                  {selectedPatient?.ayushmanEligible
                    ? "Compare with PM-JAY HBP →"
                    : "Compare with CGHS →"}
                </button>
              </div>
              {error && <p className="error-text">{error}</p>}
            </motion.section>
          )}

          {uiState === "results" && (
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
        </AnimatePresence>
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
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
