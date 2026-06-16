import { useEffect, useState } from "react";
import EligibilityCriteriaModal, {
  AAROGYA_BHADRATHA_ELIGIBILITY_SECTIONS,
  AAROGYA_BHADRATHA_COVERAGE_LIMITS,
  PMJAY_ELIGIBILITY_SECTIONS,
} from "./EligibilityCriteriaModal";
import { getStateOptions, isTelanganaState } from "../services/locations";

export const GENDER_OPTIONS = [
  { id: "male", label: "Male" },
  { id: "female", label: "Female" },
  { id: "other", label: "Other" },
  { id: "prefer_not_to_say", label: "Prefer not to say" },
];

export const emptyPatientForm = () => ({
  name: "",
  age: "",
  gender: "",
  state: "",
  ayushmanEligible: false,
  aarogyaBhadrathaEligible: false,
  savePastBills: false,
});

export function genderLabel(gender) {
  return (
    GENDER_OPTIONS.find((option) => option.id === gender)?.label || gender || "—"
  );
}

const STATE_OPTIONS = getStateOptions();

export default function PatientForm({
  form,
  setForm,
  onSubmit,
  onCancel,
  submitLabel,
  saving,
  error,
  info,
}) {
  const [activeModal, setActiveModal] = useState(null);

  const showAarogyaCard = isTelanganaState(form.state);

  // When the patient is no longer in Telangana, the Aarogya Bhadratha scheme
  // does not apply, so reset its eligibility flag.
  useEffect(() => {
    if (!showAarogyaCard && form.aarogyaBhadrathaEligible) {
      setForm((prev) => ({ ...prev, aarogyaBhadrathaEligible: false }));
    }
  }, [showAarogyaCard, form.aarogyaBhadrathaEligible, setForm]);

  return (
    <form className="patient-form" onSubmit={onSubmit}>
      <label className="setting-field setting-field-full">
        <span>Patient name</span>
        <input
          type="text"
          value={form.name}
          required
          placeholder="Full name"
          onChange={(event) =>
            setForm((prev) => ({ ...prev, name: event.target.value }))
          }
        />
      </label>
      <div className="comparison-settings-grid">
        <label className="setting-field">
          <span>Age</span>
          <input
            type="number"
            min="0"
            max="150"
            required
            value={form.age}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, age: event.target.value }))
            }
          />
        </label>
        <label className="setting-field">
          <span>Gender</span>
          <select
            required
            value={form.gender}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, gender: event.target.value }))
            }
          >
            <option value="">Select gender</option>
            {GENDER_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="setting-field setting-field-full">
        <span>State</span>
        <select
          value={form.state}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, state: event.target.value }))
          }
        >
          <option value="">Select state</option>
          {STATE_OPTIONS.map((stateName) => (
            <option key={stateName} value={stateName}>
              {stateName}
            </option>
          ))}
        </select>
      </label>

      <fieldset className="scheme-eligibility">
        <legend className="scheme-eligibility-title">Scheme eligibility</legend>
        <div className="scheme-card-list">
          <div className="scheme-card">
            <label className="scheme-card-checkbox">
              <input
                type="checkbox"
                checked={form.ayushmanEligible}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    ayushmanEligible: event.target.checked,
                  }))
                }
              />
              <span>Patient is eligible for Ayushman Bharat Scheme</span>
            </label>
            <button
              type="button"
              className="eligibility-learn-btn"
              onClick={() => setActiveModal("ayushman")}
            >
              Learn eligibility criteria
            </button>
          </div>

          {showAarogyaCard && (
            <div className="scheme-card">
              <label className="scheme-card-checkbox">
                <input
                  type="checkbox"
                  checked={form.aarogyaBhadrathaEligible}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      aarogyaBhadrathaEligible: event.target.checked,
                    }))
                  }
                />
                <span>Patient is eligible for Aarogya Bhadratha Scheme</span>
              </label>
              <div className="scheme-card-buttons">
                <button
                  type="button"
                  className="eligibility-learn-btn"
                  onClick={() => setActiveModal("aarogya")}
                >
                  Eligibility criteria
                </button>
                <button
                  type="button"
                  className="eligibility-learn-btn"
                  onClick={() => setActiveModal("aarogya-coverage")}
                >
                  Coverage limits
                </button>
              </div>
            </div>
          )}
        </div>
      </fieldset>

      <label className="patient-checkbox">
        <input
          type="checkbox"
          checked={form.savePastBills}
          onChange={(event) =>
            setForm((prev) => ({
              ...prev,
              savePastBills: event.target.checked,
            }))
          }
        />
        <span>Do you want to save this patient&apos;s past bills?</span>
      </label>

      <EligibilityCriteriaModal
        open={activeModal === "ayushman"}
        onClose={() => setActiveModal(null)}
        title="Ayushman Bharat PM-JAY eligibility"
        sections={PMJAY_ELIGIBILITY_SECTIONS}
      />
      <EligibilityCriteriaModal
        open={activeModal === "aarogya"}
        onClose={() => setActiveModal(null)}
        title="Aarogya Bhadratha Scheme eligibility"
        sections={AAROGYA_BHADRATHA_ELIGIBILITY_SECTIONS}
      />
      <EligibilityCriteriaModal
        open={activeModal === "aarogya-coverage"}
        onClose={() => setActiveModal(null)}
        title="Aarogya Bhadratha Coverage Limits"
        sections={AAROGYA_BHADRATHA_COVERAGE_LIMITS}
      />

      {info && <p className="auth-info">{info}</p>}
      {error && <p className="error-text">{error}</p>}
      <div className="patient-form-actions">
        {onCancel && (
          <button
            type="button"
            className="bill-editor-secondary"
            onClick={onCancel}
            disabled={saving}
          >
            Cancel
          </button>
        )}
        <button type="submit" className="analyze-btn" disabled={saving}>
          {saving ? "Saving..." : submitLabel}
        </button>
      </div>
    </form>
  );
}
