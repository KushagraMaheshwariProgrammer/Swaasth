import { getStateOptions } from "../services/locations";
import {
  emptyClinicalHistory,
  normalizeClinicalHistory,
} from "../utils/clinicalHistory";

export const GENDER_OPTIONS = [
  { id: "male", label: "Male" },
  { id: "female", label: "Female" },
  { id: "other", label: "Other" },
  { id: "prefer_not_to_say", label: "Prefer not to say" },
];

export { emptyClinicalHistory, normalizeClinicalHistory };

export const emptyPatientForm = () => ({
  name: "",
  age: "",
  gender: "",
  state: "",
  savePastBills: false,
  clinicalHistory: emptyClinicalHistory(),
});

export function patientToFormFields(patient) {
  const history = patient?.clinicalHistory || emptyClinicalHistory();
  return {
    name: patient?.name || "",
    age: patient?.age != null ? String(patient.age) : "",
    gender: patient?.gender || "",
    state: patient?.state || "",
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

function createHistoryRow(fields) {
  return fields.reduce((row, field) => ({ ...row, [field]: "" }), {});
}

function HistoryRows({ title, rows, fields, fieldLabels, onChange, disabled }) {
  const updateRow = (index, key, value) => {
    const next = rows.map((row, rowIndex) =>
      rowIndex === index ? { ...row, [key]: value } : row
    );
    onChange(next);
  };

  const addRow = () => {
    onChange([...rows, createHistoryRow(fields)]);
  };

  const removeRow = (index) => {
    onChange(rows.filter((_, rowIndex) => rowIndex !== index));
  };

  return (
    <div className="clinical-history-group">
      <div className="clinical-history-group-header">
        <h3>{title}</h3>
        <button
          type="button"
          className="bill-editor-secondary clinical-history-add-btn"
          onClick={addRow}
          disabled={disabled}
        >
          Add
        </button>
      </div>
      {rows.length === 0 && (
        <p className="clinical-history-empty">None added yet.</p>
      )}
      {rows.map((row, index) => (
        <div key={`${title}-${index}`} className="clinical-history-row">
          {fields.map((field) => (
            <label key={field} className="setting-field">
              <span>{fieldLabels[field]}</span>
              <input
                type={field === "year" ? "number" : "text"}
                min={field === "year" ? "1900" : undefined}
                max={field === "year" ? "2100" : undefined}
                value={row[field] || ""}
                placeholder={fieldLabels[field]}
                onChange={(event) => updateRow(index, field, event.target.value)}
                disabled={disabled}
              />
            </label>
          ))}
          <button
            type="button"
            className="bill-editor-secondary clinical-history-remove-btn"
            onClick={() => removeRow(index)}
            disabled={disabled}
            aria-label={`Remove ${title} row`}
          >
            Remove
          </button>
        </div>
      ))}
    </div>
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
  const history = form.clinicalHistory || emptyClinicalHistory();

  const setHistorySection = (section, rows) => {
    setForm((prev) => ({
      ...prev,
      clinicalHistory: {
        ...(prev.clinicalHistory || emptyClinicalHistory()),
        [section]: rows,
      },
    }));
  };

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

      <section className="clinical-history-section">
        <h2>Medical history</h2>
        <p className="comparison-settings-hint">
          Add long-term conditions, surgeries, and allergies. This profile history is
          always considered during audits.
        </p>
        <HistoryRows
          title="Conditions"
          rows={history.conditions || []}
          fields={["name", "year", "status"]}
          fieldLabels={{
            name: "Condition",
            year: "Year (optional)",
            status: "Status (optional)",
          }}
          onChange={(rows) => setHistorySection("conditions", rows)}
          disabled={saving}
        />
        <HistoryRows
          title="Surgeries"
          rows={history.surgeries || []}
          fields={["name", "year"]}
          fieldLabels={{
            name: "Surgery",
            year: "Year (optional)",
          }}
          onChange={(rows) => setHistorySection("surgeries", rows)}
          disabled={saving}
        />
        <HistoryRows
          title="Allergies"
          rows={history.allergies || []}
          fields={["name", "reaction"]}
          fieldLabels={{
            name: "Allergen",
            reaction: "Reaction (optional)",
          }}
          onChange={(rows) => setHistorySection("allergies", rows)}
          disabled={saving}
        />
      </section>

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
