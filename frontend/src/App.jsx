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

const TIER_OPTIONS = [
  { id: "tier_1", label: "Tier I city (e.g. metros)" },
  { id: "tier_2", label: "Tier II city" },
  { id: "tier_3", label: "Tier III city" },
];

const RATE_TYPE_OPTIONS = [
  { id: "nabh", label: "NABH accredited hospital" },
  { id: "non_nabh", label: "Non-NABH hospital" },
  { id: "super_speciality", label: "Super speciality rate" },
];
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
                title: "AI reads everything",
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
  const [tier, setTier] = useState("tier_1");
  const [rateType, setRateType] = useState("nabh");
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [loadingMessageIndex, setLoadingMessageIndex] = useState(0);
  const [loadingProgress, setLoadingProgress] = useState(8);

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
    : result?.line_items?.length
    ? "results"
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
    setSelectedFile(file);
  };

  const handleAnalyze = async () => {
    if (!selectedFile) {
      setError("Please select your hospital bill first.");
      return;
    }
    setError("");
    setIsLoading(true);
    setResult(null);
    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const params = new URLSearchParams({ tier, rate_type: rateType });
      const response = await fetch(`${API_BASE}/upload-bill?${params}`, {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || "Unable to analyze this bill.");
      }
      setLoadingProgress(100);
      setResult(payload);
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
                <p className="comparison-settings-title">CGHS comparison settings</p>
                <div className="comparison-settings-grid">
                  <label className="setting-field">
                    <span>City tier</span>
                    <select
                      value={tier}
                      onChange={(event) => setTier(event.target.value)}
                    >
                      {TIER_OPTIONS.map((option) => (
                        <option key={option.id} value={option.id}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="setting-field">
                    <span>Hospital rate type</span>
                    <select
                      value={rateType}
                      onChange={(event) => setRateType(event.target.value)}
                    >
                      {RATE_TYPE_OPTIONS.map((option) => (
                        <option key={option.id} value={option.id}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <p className="comparison-settings-hint">
                  Bills are matched against official CGHS 2025 rates for your city
                  tier, including NABH and non-NABH columns.
                </p>
              </div>

              <button type="button" className="analyze-btn" onClick={handleAnalyze}>
                Analyze Bill
              </button>
              {error && <p className="error-text">{error}</p>}
            </motion.section>
          )}

          {uiState === "loading" && (
            <motion.section
              key="loading"
              className="loading-card"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.25 }}
            >
              <div className="spinner-conic" aria-hidden="true" />
              <p className="loading-message">{LOADING_MESSAGES[loadingMessageIndex]}</p>
              <div className="loading-bar">
                <div className="loading-bar-fill" style={{ width: `${loadingProgress}%` }} />
              </div>
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
              {result?.comparison_settings && (
                <p className="comparison-context">
                  Compared using{" "}
                  <strong>{result.comparison_settings.tier}</strong> ·{" "}
                  <strong>
                    {RATE_TYPE_OPTIONS.find(
                      (o) => o.id === result.comparison_settings.rate_type
                    )?.label || result.comparison_settings.rate_type}
                  </strong>
                </p>
              )}

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
