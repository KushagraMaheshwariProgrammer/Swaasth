import { useEffect, useRef, useState } from "react";
import AarogyaResults from "./AarogyaResults";
import AarogyaHospitalDirectory from "./AarogyaHospitalDirectory";
import {
  buildAarogyaBillEntry,
  buildHospitalSearchQuery,
  compareRates,
  extractAarogyaBill,
  getDistricts,
  isSameHospitalBrand,
  searchHospitals,
  verifyHospital,
} from "../services/aarogyaBhadratha";
import {
  markLocalBillSynced,
  persistLocalBill,
  saveBill,
} from "../services/bills";

const ALLOWED_EXTENSIONS = ["pdf", "jpg", "jpeg", "png"];

const isSupportedFile = (file) => {
  const ext = file?.name?.split(".").pop()?.toLowerCase();
  return Boolean(ext && ALLOWED_EXTENSIONS.includes(ext));
};

const emptyItem = () => ({
  item_name: "",
  quantity: 1,
  unit_price: 0,
  total_price: 0,
  category: "other",
});

const recalc = (item) => {
  const quantity = Math.max(Number(item.quantity) || 0, 0);
  const unit = Math.max(Number(item.unit_price) || 0, 0);
  return { ...item, total_price: Math.round(quantity * unit * 100) / 100 };
};

export default function AarogyaFlow({
  patient,
  user,
  onChangePatient,
  onCompareWithCghs = null,
}) {
  const inputRef = useRef(null);
  const [phase, setPhase] = useState("upload");
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const [districts, setDistricts] = useState([]);

  const [ocr, setOcr] = useState(null);
  const [items, setItems] = useState([]);
  const [hospitalName, setHospitalName] = useState("");
  const [district, setDistrict] = useState("");

  const [verifyResult, setVerifyResult] = useState(null);
  const [confirmedHospital, setConfirmedHospital] = useState(null);
  const [matchInfo, setMatchInfo] = useState({ confidence: null, method: null });

  const [report, setReport] = useState(null);
  const [saveMessage, setSaveMessage] = useState("");
  const [suggestedHospitals, setSuggestedHospitals] = useState([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [suggestionsError, setSuggestionsError] = useState("");
  const [cghsLoading, setCghsLoading] = useState(false);
  const [consumableIndices, setConsumableIndices] = useState(new Set());

  useEffect(() => {
    let cancelled = false;
    getDistricts()
      .then((list) => {
        if (!cancelled) setDistricts(list || []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (phase !== "not_found") {
      return undefined;
    }

    let cancelled = false;
    (async () => {
      setSuggestionsLoading(true);
      setSuggestionsError("");
      try {
        let results = [];
        const searchQuery = buildHospitalSearchQuery(hospitalName);
        if (district) {
          const byDistrict = await searchHospitals({
            district,
            limit: 8,
          });
          results = (byDistrict.results || [])
            .filter((hospital) => !isSameHospitalBrand(hospitalName, hospital))
            .slice(0, 4);
        }
        if (!results.length && searchQuery) {
          const byName = await searchHospitals({
            query: searchQuery,
            district: district || undefined,
            limit: 6,
          });
          results = (byName.results || [])
            .filter((hospital) => !isSameHospitalBrand(hospitalName, hospital))
            .slice(0, 4);
        }
        if (!results.length && searchQuery && !district) {
          const byName = await searchHospitals({
            query: searchQuery,
            limit: 4,
          });
          results = byName.results || [];
        }
        if (!results.length && district) {
          const byDistrict = await searchHospitals({
            district,
            limit: 4,
          });
          results = byDistrict.results || [];
        }
        if (!cancelled) {
          setSuggestedHospitals(results);
        }
      } catch (err) {
        if (!cancelled) {
          setSuggestedHospitals([]);
          setSuggestionsError(
            err.message ||
              "Could not load empanelled hospitals. Check that the backend is running."
          );
        }
      } finally {
        if (!cancelled) {
          setSuggestionsLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [phase, hospitalName, district]);

  const resetAll = () => {
    setPhase("upload");
    setFile(null);
    setError("");
    setOcr(null);
    setItems([]);
    setHospitalName("");
    setDistrict("");
    setVerifyResult(null);
    setConfirmedHospital(null);
    setMatchInfo({ confidence: null, method: null });
    setReport(null);
    setSaveMessage("");
    setSuggestedHospitals([]);
    setSuggestionsLoading(false);
    setConsumableIndices(new Set());
  };

  const isNabhSuperSpecialty = (hospital) => {
    const accreditation = (hospital?.accreditation || "").toUpperCase();
    return accreditation.includes("SUPER");
  };

  const toggleConsumable = (index) => {
    setConsumableIndices((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const handleCompareWithCghs = async () => {
    if (!onCompareWithCghs) {
      return;
    }
    setError("");
    setCghsLoading(true);
    try {
      await onCompareWithCghs({
        items: validItems(),
        hospitalName: hospitalName.trim(),
        district,
        ocr,
        file,
      });
    } catch (err) {
      setError(err.message || "Could not start CGHS comparison.");
      setCghsLoading(false);
    }
  };

  const handleFile = (selected) => {
    if (!selected) return;
    if (!isSupportedFile(selected)) {
      setError("Please upload a valid PDF, JPG, JPEG, or PNG file.");
      return;
    }
    setError("");
    setFile(selected);
  };

  const handleExtract = async () => {
    if (!file) {
      setError("Please select your hospital bill first.");
      return;
    }
    setError("");
    setPhase("extracting");
    try {
      const result = await extractAarogyaBill(file);
      const extractedItems = (result.line_items || []).map((item) => ({
        ...emptyItem(),
        ...item,
      }));
      if (!extractedItems.length) {
        throw new Error("No bill items were detected on this bill.");
      }
      setOcr(result);
      setItems(extractedItems);
      setHospitalName(result.ocr_hospital_name || "");
      setPhase("edit");
    } catch (err) {
      setError(err.message || "Could not read this bill. Try another file or retry.");
      setPhase("upload");
    }
  };

  const updateItem = (index, field, value) => {
    setItems((prev) =>
      prev.map((item, i) => {
        if (i !== index) return item;
        const next = { ...item, [field]: value };
        return field === "quantity" || field === "unit_price" ? recalc(next) : next;
      })
    );
  };

  const removeItem = (index) =>
    setItems((prev) => prev.filter((_, i) => i !== index));
  const addItem = () => setItems((prev) => [...prev, emptyItem()]);

  const validItems = () =>
    items
      .map((item) => ({
        item_name: String(item.item_name || "").trim(),
        quantity: Math.max(Number(item.quantity) || 0, 0) || 1,
        unit_price: Math.max(Number(item.unit_price) || 0, 0),
        total_price: Math.max(Number(item.total_price) || 0, 0),
        category: item.category || "other",
      }))
      .filter((item) => item.item_name);

  const handleVerify = async () => {
    if (!hospitalName.trim()) {
      setError("Enter the hospital name from the bill, or search the directory below.");
      setPhase("not_found");
      return;
    }
    if (!validItems().length) {
      setError("Add at least one bill item with a name.");
      return;
    }
    setError("");
    setPhase("verifying");
    try {
      const result = await verifyHospital({
        hospitalName: hospitalName.trim(),
        district,
      });
      setVerifyResult(result);
      if (result.empanelment_status === "empanelled" && result.matched_hospital) {
        setConfirmedHospital(result.matched_hospital);
        setMatchInfo({
          confidence: result.match_confidence,
          method: result.match_method,
        });
        setPhase("empanelled");
      } else if (result.empanelment_status === "multiple") {
        setPhase("multiple");
      } else {
        setPhase("not_found");
      }
    } catch (err) {
      setError(err.message || "Could not verify the hospital. Please retry.");
      setPhase("edit");
    }
  };

  const confirmHospital = (hospital, info = {}) => {
    setConfirmedHospital(hospital);
    setMatchInfo({
      confidence: info.confidence ?? hospital.match_confidence ?? 1.0,
      method: info.method ?? "user_confirmed",
    });
    setError("");
    setPhase("empanelled");
  };

  const handleCompare = async () => {
    if (!confirmedHospital?.id) {
      setError("Confirm an empanelled hospital first.");
      return;
    }
    setError("");
    setPhase("comparing");
    try {
      const list = validItems();
      const originalTotal = list.reduce(
        (sum, item) => sum + (item.total_price || 0),
        0
      );
      const generated = await compareRates({
        hospital_id: confirmedHospital.id,
        patient: {
          name: patient?.name || "",
          state: patient?.state || "Telangana",
          aarogya_bhadratha_eligible: true,
          id: patient?.id || null,
        },
        line_items: list,
        bill: {
          filename: ocr?.filename || file?.name || "bill",
          bill_date: ocr?.bill_date || null,
          original_total: Math.round(originalTotal * 100) / 100,
          file_type: ocr?.file_type || null,
        },
        ocr_hospital_name: hospitalName.trim(),
        ocr_text: ocr?.ocr_text || "",
        match_confidence: matchInfo.confidence,
        match_method: matchInfo.method,
        consumable_indices: Array.from(consumableIndices),
      });
      setReport(generated);
      setPhase("results");
      persistReportToHistory(generated);
    } catch (err) {
      setError(err.message || "Could not complete the rate comparison. Please retry.");
      setPhase("empanelled");
    }
  };

  const persistReportToHistory = (generated) => {
    if (!user || !patient?.savePastBills) {
      return;
    }
    try {
      const entry = buildAarogyaBillEntry(generated, patient);
      const localId = persistLocalBill(user.uid, entry);
      saveBill(user.uid, entry, { localId, patientId: patient?.id || null })
        .then((firestoreId) => {
          markLocalBillSynced(user.uid, localId, firestoreId);
          setSaveMessage("Aarogya Bhadratha report saved to your account.");
        })
        .catch(() => {
          setSaveMessage(
            "Report saved on this device. Open Past bills to retry syncing to your account."
          );
        });
    } catch {
      setSaveMessage("Could not save the report to history on this device.");
    }
  };

  const patientBanner = (
    <div className="patient-selected-banner patient-selected-banner-compact">
      <p>
        Patient: <strong>{patient?.name}</strong>
        {patient?.age != null ? ` · ${patient.age} yrs` : ""} · Telangana ·{" "}
        <strong>Aarogya Bhadratha</strong>
      </p>
      {onChangePatient && (
        <button
          type="button"
          className="bill-editor-secondary patient-change-btn"
          onClick={onChangePatient}
        >
          Change patient
        </button>
      )}
    </div>
  );

  // ---- Loading phases ---- //
  if (phase === "extracting" || phase === "verifying" || phase === "comparing") {
    const message =
      phase === "extracting"
        ? "Running OCR and extracting bill items…"
        : phase === "verifying"
        ? "Verifying hospital against the Aarogya Bhadratha empanelled list…"
        : "Comparing bill items with Aarogya Bhadratha approved rates…";
    return (
      <section className="loading-card">
        <div className="spinner-conic" aria-hidden="true" />
        <p className="loading-message">{message}</p>
      </section>
    );
  }

  // ---- Results ---- //
  if (phase === "results" && report) {
    return (
      <section className="results-shell">
        {saveMessage && <p className="save-message">{saveMessage}</p>}
        <AarogyaResults
          report={report}
          toolbar={
            <div className="abh-toolbar">
              <button type="button" className="bill-editor-secondary" onClick={() => setPhase("edit")}>
                ← Edit bill items
              </button>
              <button type="button" className="bill-editor-secondary" onClick={resetAll}>
                Analyze another bill
              </button>
            </div>
          }
        />
      </section>
    );
  }

  return (
    <section className="upload-card abh-flow">
      {patientBanner}
      <p className="comparison-settings-title">Aarogya Bhadratha Scheme analysis</p>

      {/* ---- Upload ---- */}
      {phase === "upload" && (
        <>
          <button
            type="button"
            className="upload-zone"
            onClick={() => inputRef.current?.click()}
          >
            <div className="upload-icon">↑</div>
            <p className="upload-title">Upload the hospital bill</p>
            <p className="upload-subtitle">Supports PDF, JPG, PNG</p>
            {file && <p className="file-name">{file.name}</p>}
          </button>
          <input
            ref={inputRef}
            className="hidden-input"
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
            onChange={(event) => {
              handleFile(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
          <button type="button" className="analyze-btn" onClick={handleExtract}>
            Analyze with Aarogya Bhadratha
          </button>
        </>
      )}

      {/* ---- Edit + hospital ---- */}
      {phase === "edit" && (
        <div className="abh-edit">
          <p className="comparison-settings-hint">
            Review the scanned items, then we'll verify the hospital against the
            Aarogya Bhadratha empanelled list.
          </p>
          <label className="setting-field setting-field-full">
            <span>Hospital name (from bill)</span>
            <input
              type="text"
              value={hospitalName}
              placeholder="As shown on the bill"
              onChange={(event) => setHospitalName(event.target.value)}
            />
          </label>
          <label className="setting-field setting-field-full">
            <span>Hospital district (helps matching)</span>
            <select value={district} onChange={(event) => setDistrict(event.target.value)}>
              <option value="">Select district (optional)</option>
              {districts.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>

          <ul className="bill-editor-list">
            {items.map((item, index) => (
              <li key={`abh-item-${index}`} className="bill-editor-row">
                <div className="bill-editor-row-top">
                  <label className="bill-editor-field bill-editor-field-grow">
                    <span>Item</span>
                    <input
                      type="text"
                      value={item.item_name}
                      onChange={(event) => updateItem(index, "item_name", event.target.value)}
                    />
                  </label>
                  <button
                    type="button"
                    className="bill-editor-remove"
                    onClick={() => removeItem(index)}
                    aria-label={`Remove item ${index + 1}`}
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
                      value={item.quantity}
                      onChange={(event) => updateItem(index, "quantity", Number(event.target.value))}
                    />
                  </label>
                  <label className="bill-editor-field">
                    <span>Unit price (₹)</span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={item.unit_price}
                      onChange={(event) => updateItem(index, "unit_price", Number(event.target.value))}
                    />
                  </label>
                  <label className="bill-editor-field">
                    <span>Total (₹)</span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={item.total_price}
                      onChange={(event) => updateItem(index, "total_price", Number(event.target.value))}
                    />
                  </label>
                </div>
              </li>
            ))}
          </ul>
          <button type="button" className="bill-editor-add" onClick={addItem}>
            + Add line item
          </button>

          <div className="bill-editor-actions">
            <button type="button" className="bill-editor-secondary" onClick={resetAll}>
              Upload different bill
            </button>
            <button type="button" className="analyze-btn bill-editor-primary" onClick={handleVerify}>
              Verify hospital →
            </button>
          </div>
        </div>
      )}

      {/* ---- Multiple candidates ---- */}
      {phase === "multiple" && (
        <div className="abh-multiple">
          <p className="comparison-settings-hint">
            We found more than one possible hospital. Select the correct one to
            continue.
          </p>
          <ul className="abh-hospital-list">
            {(verifyResult?.candidates || []).map((hospital) => (
              <li key={hospital.id} className="abh-hospital-card">
                <div className="abh-hospital-card-body">
                  <strong>{hospital.name}</strong>
                  <p className="abh-hospital-district">{hospital.district}</p>
                  <p className="abh-hospital-address">{hospital.address}</p>
                  <p className="abh-hospital-spec">
                    {(hospital.specialities && hospital.specialities.slice(0, 4).join(", ")) ||
                      hospital.specialities_text ||
                      "Speciality not listed"}
                  </p>
                </div>
                <button
                  type="button"
                  className="bill-editor-secondary abh-hospital-select"
                  onClick={() =>
                    confirmHospital(hospital, {
                      confidence: hospital.match_confidence,
                      method: "user_confirmed",
                    })
                  }
                >
                  This is the hospital
                </button>
              </li>
            ))}
          </ul>
          <button
            type="button"
            className="bill-editor-secondary"
            onClick={() => setPhase("not_found")}
          >
            None of these
          </button>
        </div>
      )}

      {/* ---- Not found ---- */}
      {phase === "not_found" && (
        <div className="abh-not-found">
          <p className="abh-warn-banner">
            {hospitalName.trim()
              ? `"${hospitalName.trim()}" is not empanelled under Aarogya Bhadratha.`
              : "This hospital was not found in the Aarogya Bhadratha empanelled hospital list."}
          </p>

          <div className="abh-ineligible-options">
            <p className="abh-ineligible-lead">
              You&apos;re eligible for Aarogya Bhadratha, but this hospital
              doesn&apos;t participate in the scheme. You can:
            </p>

            <div className="abh-ineligible-actions">
              <section className="abh-ineligible-panel">
                <h3 className="abh-ineligible-panel-title">
                  Switch to an empanelled hospital
                </h3>
                <p className="comparison-settings-hint">
                  {district
                    ? `Suggested Aarogya Bhadratha hospitals in ${district}:`
                    : "Suggested empanelled hospitals near your bill:"}
                </p>
                {suggestionsLoading ? (
                  <p className="auth-info">Finding nearby empanelled hospitals…</p>
                ) : suggestionsError ? (
                  <p className="error-text">{suggestionsError}</p>
                ) : suggestedHospitals.length ? (
                  <ul className="abh-hospital-list abh-suggested-list">
                    {suggestedHospitals.map((hospital) => (
                      <li key={hospital.id} className="abh-hospital-card">
                        <div className="abh-hospital-card-body">
                          <strong>{hospital.name}</strong>
                          <p className="abh-hospital-district">{hospital.district}</p>
                          <p className="abh-hospital-address">{hospital.address}</p>
                        </div>
                        <button
                          type="button"
                          className="bill-editor-secondary abh-hospital-select"
                          onClick={() =>
                            confirmHospital(hospital, { method: "user_confirmed" })
                          }
                        >
                          Use this hospital
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="comparison-settings-hint">
                    Search the directory below for an empanelled hospital in your
                    area.
                  </p>
                )}
              </section>

              {onCompareWithCghs && (
                <section className="abh-ineligible-panel abh-ineligible-panel-alt">
                  <h3 className="abh-ineligible-panel-title">
                    Stay at this hospital
                  </h3>
                  <p className="comparison-settings-hint">
                    Compare your bill against CGHS government benchmark rates
                    instead. This won&apos;t use Aarogya Bhadratha scheme rates.
                  </p>
                  <button
                    type="button"
                    className="analyze-btn abh-cghs-fallback-btn"
                    onClick={handleCompareWithCghs}
                    disabled={cghsLoading}
                  >
                    {cghsLoading
                      ? "Comparing with CGHS rates…"
                      : "Compare with CGHS rates →"}
                  </button>
                </section>
              )}
            </div>
          </div>

          <p className="comparison-settings-hint">
            Or search all eligible Aarogya Bhadratha hospitals below.
          </p>
          <AarogyaHospitalDirectory
            initialDistrict={district}
            onSelect={(hospital) =>
              confirmHospital(hospital, { method: "user_confirmed" })
            }
            selectLabel="Use this hospital"
          />
          <div className="bill-editor-actions">
            <button type="button" className="bill-editor-secondary" onClick={() => setPhase("edit")}>
              ← Back to bill items
            </button>
          </div>
        </div>
      )}

      {/* ---- Empanelled confirmation ---- */}
      {phase === "empanelled" && confirmedHospital && (
        <div className="abh-empanelled">
          <p className="abh-empanel-badge">
            This hospital is empanelled under the Aarogya Bhadratha Scheme.
          </p>
          <div className="abh-hospital-card abh-hospital-card-detail">
            <strong>{confirmedHospital.name}</strong>
            <p className="abh-hospital-district">District: {confirmedHospital.district}</p>
            <p className="abh-hospital-address">{confirmedHospital.address}</p>
            <p className="abh-hospital-spec">
              {(confirmedHospital.specialities &&
                confirmedHospital.specialities.join(", ")) ||
                confirmedHospital.specialities_text ||
                "Speciality not listed"}
            </p>
            <p className="abh-hospital-meta">
              {confirmedHospital.accreditation || ""}
              {confirmedHospital.hospital_code
                ? ` · Code ${confirmedHospital.hospital_code}`
                : ` · Ref ${confirmedHospital.ref_no || "—"}`}
              {matchInfo.confidence != null
                ? ` · Match ${Math.round(Number(matchInfo.confidence) * 100)}%`
                : ""}
            </p>
          </div>

          {/* Consumables selection for NABH Super Specialty */}
          {isNabhSuperSpecialty(confirmedHospital) && (
            <div className="abh-consumables-section">
              <h4 className="abh-consumables-title">Mark Consumables (Optional)</h4>
              <p className="comparison-settings-hint">
                For NABH Super Specialty hospitals, consumables like implants, stents, and mesh
                are reimbursed at actual cost (on top of package rates). Mark any applicable items below.
              </p>
              <ul className="abh-consumables-list">
                {items.map((item, index) => {
                  const itemName = String(item.item_name || "").trim();
                  if (!itemName) return null;
                  return (
                    <li key={`consumable-${index}`} className="abh-consumable-item">
                      <label className="abh-consumable-label">
                        <input
                          type="checkbox"
                          checked={consumableIndices.has(index)}
                          onChange={() => toggleConsumable(index)}
                        />
                        <span className="abh-consumable-name">{itemName}</span>
                        <span className="abh-consumable-price">
                          ₹{Number(item.total_price || 0).toLocaleString("en-IN")}
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
              {consumableIndices.size > 0 && (
                <p className="abh-consumables-note">
                  {consumableIndices.size} item{consumableIndices.size > 1 ? "s" : ""} marked as
                  consumable — will be passed at actual cost.
                </p>
              )}
            </div>
          )}

          <div className="bill-editor-actions">
            <button type="button" className="bill-editor-secondary" onClick={() => setPhase("edit")}>
              ← Edit items
            </button>
            <button type="button" className="analyze-btn bill-editor-primary" onClick={handleCompare}>
              Compare with Aarogya Bhadratha rates →
            </button>
          </div>
        </div>
      )}

      {error && <p className="error-text">{error}</p>}
    </section>
  );
}
