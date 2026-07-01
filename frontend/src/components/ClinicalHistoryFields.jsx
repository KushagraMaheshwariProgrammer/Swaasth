import { emptyClinicalHistory } from "../utils/clinicalHistory";

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

export default function ClinicalHistoryFields({
  history,
  onChange,
  disabled = false,
  showHeading = true,
}) {
  const clinicalHistory = history || emptyClinicalHistory();

  const setHistorySection = (section, rows) => {
    onChange({
      ...clinicalHistory,
      [section]: rows,
    });
  };

  return (
    <>
      {showHeading && (
        <>
          <h2>Medical history</h2>
          <p className="comparison-settings-hint">
            Add long-term conditions, surgeries, and allergies. This profile history
            is always considered during audits.
          </p>
        </>
      )}
      <HistoryRows
        title="Conditions"
        rows={clinicalHistory.conditions || []}
        fields={["name", "year", "status"]}
        fieldLabels={{
          name: "Condition",
          year: "Year (optional)",
          status: "Status (optional)",
        }}
        onChange={(rows) => setHistorySection("conditions", rows)}
        disabled={disabled}
      />
      <HistoryRows
        title="Surgeries"
        rows={clinicalHistory.surgeries || []}
        fields={["name", "year"]}
        fieldLabels={{
          name: "Surgery",
          year: "Year (optional)",
        }}
        onChange={(rows) => setHistorySection("surgeries", rows)}
        disabled={disabled}
      />
      <HistoryRows
        title="Allergies"
        rows={clinicalHistory.allergies || []}
        fields={["name", "reaction"]}
        fieldLabels={{
          name: "Allergen",
          reaction: "Reaction (optional)",
        }}
        onChange={(rows) => setHistorySection("allergies", rows)}
        disabled={disabled}
      />
    </>
  );
}
