import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  BrowserRouter,
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";

const API_BASE = "http://127.0.0.1:8000";
const ALLOWED_EXTENSIONS = ["pdf", "jpg", "jpeg", "png"];

const HOSPITAL_TYPE_OPTIONS = [
  { id: "general", label: "General hospital" },
  { id: "speciality", label: "Speciality hospital" },
];

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

const formatCurrency = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "--";
  }
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value));
};

const isSupportedFile = (file) => {
  const ext = file.name.split(".").pop()?.toLowerCase();
  return Boolean(ext && ALLOWED_EXTENSIONS.includes(ext));
};

const getFlagMeta = (flag) => {
  if (flag === "overpriced") {
    return {
      badgeLabel: "Overpriced",
      badgeClass: "status-pill status-red",
      cardClass: "result-card result-overpriced",
    };
  }
  if (flag === "acceptable") {
    return {
      badgeLabel: "Acceptable",
      badgeClass: "status-pill status-green",
      cardClass: "result-card result-acceptable",
    };
  }
  return {
    badgeLabel: "No Data",
    badgeClass: "status-pill status-neutral",
    cardClass: "result-card result-neutral",
  };
};

const getAuditSeverityMeta = (severity) => {
  if (severity === "HIGH") {
    return {
      badgeLabel: "High",
      badgeClass: "status-pill status-red",
      cardClass: "audit-flag-card audit-flag-high",
    };
  }
  if (severity === "MEDIUM") {
    return {
      badgeLabel: "Medium",
      badgeClass: "status-pill status-amber",
      cardClass: "audit-flag-card audit-flag-medium",
    };
  }
  return {
    badgeLabel: "Low",
    badgeClass: "status-pill status-neutral",
    cardClass: "audit-flag-card audit-flag-low",
  };
};

const getAuditRiskMeta = (riskLevel) => {
  if (riskLevel === "HIGH") {
    return { label: "High Risk", className: "audit-risk audit-risk-high" };
  }
  if (riskLevel === "MEDIUM") {
    return { label: "Medium Risk", className: "audit-risk audit-risk-medium" };
  }
  return { label: "Low Risk", className: "audit-risk audit-risk-low" };
};

function CountUp({ value, isCurrency = false, duration = 1200 }) {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    let frameId;
    let startTime;
    const target = Number(value) || 0;

    const tick = (now) => {
      if (!startTime) {
        startTime = now;
      }
      const progress = Math.min((now - startTime) / duration, 1);
      setDisplayValue(target * progress);
      if (progress < 1) {
        frameId = window.requestAnimationFrame(tick);
      }
    };

    frameId = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frameId);
  }, [duration, value]);

  return isCurrency ? formatCurrency(displayValue) : Math.round(displayValue);
}

function LandingPage() {
  const navigate = useNavigate();

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
        <p>Free for Indian patients</p>
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
              onClick={() => navigate("/check")}
            >
              Check My Bill →
            </button>
            <div className="trust-inline">
              <span>✓ Free forever</span>
              <span>•</span>
              <span>✓ No signup needed</span>
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
          India · No data stored · Built with ❤️ for India
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
  const inputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [states, setStates] = useState([]);
  const [cities, setCities] = useState([]);
  const [stateCode, setStateCode] = useState("");
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

  useEffect(() => {
    const loadStates = async () => {
      try {
        const response = await fetch(`${API_BASE}/locations/states`);
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload?.detail || "Unable to load states.");
        }
        setStates(payload.states ?? []);
      } catch (err) {
        setLocationError(err.message || "Unable to load state list.");
      }
    };
    loadStates();
  }, []);

  useEffect(() => {
    if (!stateCode) {
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
          `${API_BASE}/locations/cities?state_code=${encodeURIComponent(stateCode)}`
        );
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload?.detail || "Unable to load cities.");
        }
        setCities(payload.cities ?? []);
      } catch (err) {
        setCities([]);
        setLocationError(err.message || "Unable to load cities for this state.");
      } finally {
        setIsLoadingCities(false);
      }
    };

    loadCities();
  }, [stateCode]);

  useEffect(() => {
    if (!city) {
      setResolvedTier(null);
      return undefined;
    }
    const selected = cities.find((entry) => entry.name === city);
    if (selected) {
      setResolvedTier(selected);
    }
  }, [city, cities]);

  const summary = useMemo(() => {
    const lineItems = result?.line_items ?? [];
    return lineItems.reduce(
      (acc, item) => {
        const charged = Number(item.total_price ?? 0) || 0;
        const diff = Number(item.price_difference ?? 0) || 0;
        return {
          totalCharged: acc.totalCharged + charged,
          totalOvercharged: acc.totalOvercharged + Math.max(diff, 0),
          itemsFlagged: acc.itemsFlagged + (item.flag === "overpriced" ? 1 : 0),
        };
      },
      { totalCharged: 0, totalOvercharged: 0, itemsFlagged: 0 }
    );
  }, [result]);

  useEffect(() => {
    if (!isLoading) {
      setLoadingMessageIndex(0);
      setLoadingProgress(8);
      return undefined;
    }
    const messageTimer = window.setInterval(() => {
      setLoadingMessageIndex((prev) => (prev + 1) % LOADING_MESSAGES.length);
    }, 2000);
    const progressTimer = window.setInterval(() => {
      setLoadingProgress((prev) => Math.min(prev + 3.5, 92));
    }, 260);
    return () => {
      window.clearInterval(messageTimer);
      window.clearInterval(progressTimer);
    };
  }, [isLoading]);

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

    if (!stateCode || !city) {
      setError("Location settings are missing. Please upload the bill again.");
      return;
    }

    setError("");
    setIsComparing(true);

    try {
      const response = await fetch(`${API_BASE}/compare-bill`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          line_items: validItems,
          state_code: stateCode,
          city,
          hospital_type: hospitalType,
          hospital_name: hospitalNameEdit.trim() || null,
          filename: scanMeta?.filename,
          file_type: scanMeta?.file_type,
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
    } catch (err) {
      setError(err.message || "Something went wrong during comparison.");
    } finally {
      setIsComparing(false);
    }
  };

  const handleAnalyze = async () => {
    if (!selectedFile) {
      setError("Please select your hospital bill first.");
      return;
    }
    if (!stateCode || !city) {
      setError("Please select the state and city where the hospital is located.");
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
        state_code: stateCode,
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
        <Link to="/" className="back-link">
          ← Back
        </Link>

        <header className="check-header">
          <h1>Upload your hospital bill</h1>
          <p>We&apos;ll analyze it in seconds.</p>
        </header>

        <AnimatePresence mode="wait">
          {uiState === "upload" && (
            <motion.section
              key="upload"
              className="upload-card"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.25 }}
            >
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

              <div className="comparison-settings">
                <p className="comparison-settings-title">Hospital location</p>
                <div className="comparison-settings-grid">
                  <label className="setting-field">
                    <span>State</span>
                    <select
                      value={stateCode}
                      onChange={(event) => setStateCode(event.target.value)}
                    >
                      <option value="">Select state</option>
                      {states.map((state) => (
                        <option key={state.code} value={state.code}>
                          {state.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="setting-field">
                    <span>City</span>
                    <select
                      value={city}
                      disabled={!stateCode || isLoadingCities}
                      onChange={(event) => setCity(event.target.value)}
                    >
                      <option value="">
                        {isLoadingCities
                          ? "Loading cities..."
                          : stateCode
                          ? "Select city"
                          : "Select state first"}
                      </option>
                      {cities.map((entry) => (
                        <option key={entry.name} value={entry.name}>
                          {entry.name}
                        </option>
                      ))}
                    </select>
                  </label>
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
                  ? "Comparing with CGHS rates..."
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
                  Compare with CGHS →
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
              {result?.hospital?.name_from_bill && (
                <p className="comparison-context">
                  Hospital on bill: <strong>{result.hospital.name_from_bill}</strong>
                  {result.hospital.is_accredited != null && (
                    <>
                      {" · "}
                      NABH:{" "}
                      <strong>
                        {result.hospital.is_accredited
                          ? `Accredited (${result.hospital.accreditation_status})`
                          : "Not found in NABH registry"}
                      </strong>
                      {result.hospital.matched_registry_name &&
                        result.hospital.approximate_match && (
                          <> · matched as {result.hospital.matched_registry_name}</>
                        )}
                    </>
                  )}
                </p>
              )}

              {result?.comparison_settings && (
                <p className="comparison-context">
                  {result.comparison_settings.state_name &&
                    result.comparison_settings.city && (
                      <>
                        Location:{" "}
                        <strong>
                          {result.comparison_settings.city},{" "}
                          {result.comparison_settings.state_name}
                        </strong>
                        {" · "}
                      </>
                    )}
                  Tier:{" "}
                  <strong>
                    {result.comparison_settings.tier_label ||
                      result.comparison_settings.tier}
                  </strong>
                  {" · "}
                  <strong>
                    {HOSPITAL_TYPE_OPTIONS.find(
                      (o) => o.id === result.comparison_settings.hospital_type
                    )?.label || result.comparison_settings.hospital_type}
                  </strong>
                  {" · "}
                  <strong>
                    {result.comparison_settings.rate_type_label ||
                      result.comparison_settings.rate_type}
                  </strong>
                </p>
              )}

              <div className="results-toolbar">
                <button
                  type="button"
                  className="bill-editor-secondary"
                  onClick={() => {
                    if (result?.line_items?.length) {
                      setEditableItems(result.line_items.map(normalizeLineItem));
                    }
                    setResult(null);
                    setError("");
                  }}
                >
                  ← Edit bill items
                </button>
              </div>

              <article className="summary-banner">
                <div className="summary-stat">
                  <p>Total Charged</p>
                  <h3>
                    <CountUp value={summary.totalCharged} isCurrency />
                  </h3>
                </div>
                <div className="summary-stat summary-focus">
                  <p>Overcharged By</p>
                  <h3>
                    <CountUp value={summary.totalOvercharged} isCurrency />
                  </h3>
                </div>
                <div className="summary-stat summary-flagged">
                  <p>Items Flagged</p>
                  <h3>
                    <CountUp value={summary.itemsFlagged} />
                  </h3>
                </div>
              </article>

              <div className="results-grid">
                {result.line_items.map((item, index) => {
                  const meta = getFlagMeta(item.flag);
                  return (
                    <article
                      key={`${item.item_name || "item"}-${index}`}
                      className={meta.cardClass}
                    >
                      <div className="result-top">
                        <h4>{item.item_name || "--"}</h4>
                        <span className={meta.badgeClass}>{meta.badgeLabel}</span>
                      </div>
                      {item.matched_reference_item && (
                        <p className="matched-reference">
                          Matched: {item.matched_reference_item}
                          {item.cghs_code ? ` (${item.cghs_code})` : ""}
                          {item.approximate_match ? " · approximate" : ""}
                        </p>
                      )}
                      <div className="result-metrics">
                        <div>
                          <p>Charged</p>
                          <h5>{formatCurrency(item.total_price)}</h5>
                        </div>
                        <div>
                          <p>CGHS Rate</p>
                          <h5>{formatCurrency(item.cghs_rate)}</h5>
                        </div>
                        <div>
                          <p>Difference</p>
                          <h5>{formatCurrency(item.price_difference)}</h5>
                        </div>
                      </div>
                      {(item.non_nabh_rate != null || item.nabh_rate != null) && (
                        <p className="rate-breakdown">
                          Non-NABH {formatCurrency(item.non_nabh_rate)} · NABH{" "}
                          {formatCurrency(item.nabh_rate)} · Super speciality{" "}
                          {formatCurrency(item.super_speciality_rate)}
                        </p>
                      )}
                    </article>
                  );
                })}
              </div>

              <section className="audit-section">
                <div className="audit-section-header">
                  <h3>Suspicious / Unnecessary Charges</h3>
                  {result?.audit_flags && (
                    <div className="audit-summary-badges">
                      <span className={getAuditRiskMeta(result.audit_flags.risk_level).className}>
                        {getAuditRiskMeta(result.audit_flags.risk_level).label}
                      </span>
                      <span className="audit-flag-count">
                        {result.audit_flags.flags_count ?? 0} flag
                        {(result.audit_flags.flags_count ?? 0) === 1 ? "" : "s"}
                      </span>
                    </div>
                  )}
                </div>

                {result?.audit_flags?.flags?.length ? (
                  <div className="audit-flags-grid">
                    {result.audit_flags.flags.map((flag, index) => {
                      const meta = getAuditSeverityMeta(flag.severity);
                      return (
                        <article
                          key={`${flag.type || "flag"}-${flag.item || "item"}-${index}`}
                          className={meta.cardClass}
                        >
                          <div className="result-top">
                            <h4>{flag.item || "--"}</h4>
                            <span className={meta.badgeClass}>{meta.badgeLabel}</span>
                          </div>
                          <p className="audit-flag-type">{flag.type?.replaceAll("_", " ") || "--"}</p>
                          <p className="audit-flag-reason">{flag.reason}</p>
                          <p className="audit-flag-recommendation">
                            <strong>Recommendation:</strong> {flag.recommendation}
                          </p>
                        </article>
                      );
                    })}
                  </div>
                ) : (
                  <p className="audit-empty-state">
                    No suspicious repetitions or unnecessary package-component charges detected.
                  </p>
                )}
              </section>
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
        <Route path="/check" element={<CheckPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
