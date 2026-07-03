import { useEffect, useState } from "react";
import LocationSearchPicker from "./LocationSearchPicker";
import { getCities, getStateOptions } from "../services/locations";
import {
  emptyClinicalHistory,
  normalizeClinicalHistory,
} from "../utils/clinicalHistory";
import ClinicalHistoryFields from "./ClinicalHistoryFields";
import {
  deriveAgeFromBirthYear,
  getCurrentYear,
} from "../utils/patientAge";

export const GENDER_OPTIONS = [
  { id: "male", label: "Male" },
  { id: "female", label: "Female" },
  { id: "other", label: "Other" },
  { id: "prefer_not_to_say", label: "Prefer not to say" },
];

export { emptyClinicalHistory, normalizeClinicalHistory };

export const emptyPatientForm = () => ({
  name: "",
  birthYear: "",
  gender: "",
  state: "",
  city: "",
  savePastBills: false,
  clinicalHistory: emptyClinicalHistory(),
});

export function patientToFormFields(patient) {
  const history = patient?.clinicalHistory || emptyClinicalHistory();
  const birthYear =
    patient?.birthYear != null
      ? String(patient.birthYear)
      : patient?.age != null
      ? String(getCurrentYear() - Number(patient.age))
      : "";
  return {
    name: patient?.name || "",
    birthYear,
    gender: patient?.gender || "",
    state: patient?.state || "",
    city: patient?.city || "",
    savePastBills: Boolean(patient?.savePastBills),
    clinicalHistory: {
      conditions: (history.conditions || []).map((item) => ({
        name: item?.name || "",
        year: item?.year != null ? String(item.year) : "",
        status: item?.status || "",
      })),
      surgeries: (history.surgeries || []).map((item) => ({
        name: item?.name || "",
        year: item?.year != null ? String(item.year) : "",
      })),
      allergies: (history.allergies || []).map((item) => ({
        name: item?.name || "",
        reaction: item?.reaction || "",
      })),
    },
  };
}

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
  showClinicalHistory = true,
}) {
  const derivedAge = deriveAgeFromBirthYear(form.birthYear);
  const currentYear = getCurrentYear();
  const [cities, setCities] = useState(() => getCities(form.state));

  useEffect(() => {
    if (!form.state) {
      setCities([]);
      setForm((prev) => (prev.city ? { ...prev, city: "" } : prev));
      return;
    }
    const nextCities = getCities(form.state);
    setCities(nextCities);
    setForm((prev) =>
      prev.city && nextCities.includes(prev.city) ? prev : { ...prev, city: "" }
    );
  }, [form.state]);

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
          <span>Birth year</span>
          <input
            type="number"
            min="1900"
            max={currentYear}
            required
            value={form.birthYear}
            placeholder="e.g. 1985"
            onChange={(event) =>
              setForm((prev) => ({ ...prev, birthYear: event.target.value }))
            }
          />
          {derivedAge != null && (
            <span className="comparison-settings-hint">
              Approximate age: {derivedAge} yrs
            </span>
          )}
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
      <div className="comparison-settings-grid">
        <label className="setting-field">
          <span>State/UT</span>
          <select
            required
            value={form.state}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, state: event.target.value }))
            }
          >
            <option value="">Select state/UT</option>
            {STATE_OPTIONS.map((stateName) => (
              <option key={stateName} value={stateName}>
                {stateName}
              </option>
            ))}
          </select>
        </label>
        <LocationSearchPicker
          label="City"
          items={cities}
          value={form.city}
          onSelect={(city) => setForm((prev) => ({ ...prev, city }))}
          disabled={!form.state}
          placeholder="Select city"
          emptyLabel={
            form.state ? "No cities available" : "Select state/UT first"
          }
        />
      </div>

      {showClinicalHistory && (
        <section className="clinical-history-section">
          <ClinicalHistoryFields
            history={form.clinicalHistory}
            onChange={(clinicalHistory) =>
              setForm((prev) => ({ ...prev, clinicalHistory }))
            }
            disabled={saving}
          />
        </section>
      )}

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
