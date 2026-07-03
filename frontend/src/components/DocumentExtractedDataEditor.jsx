const CATEGORY_OPTIONS = [
  { id: "medicine", label: "Medicine" },
  { id: "test", label: "Test" },
  { id: "procedure", label: "Procedure" },
  { id: "other", label: "Other" },
];

function NamedItemList({ label, items, onChange, addLabel }) {
  const updateItem = (index, value) => {
    onChange(
      items.map((entry, entryIndex) =>
        entryIndex === index ? { ...entry, name: value } : entry
      )
    );
  };

  const removeItem = (index) => {
    onChange(items.filter((_, entryIndex) => entryIndex !== index));
  };

  return (
    <div className="extraction-editor-section">
      <h4>{label}</h4>
      <ul className="bill-editor-list">
        {items.map((item, index) => (
          <li key={`${label}-${index}`} className="bill-editor-row">
            <div className="bill-editor-row-top">
              <label className="bill-editor-field bill-editor-field-grow">
                <span>Name</span>
                <input
                  type="text"
                  value={item.name || ""}
                  onChange={(event) => updateItem(index, event.target.value)}
                />
              </label>
              <button
                type="button"
                className="bill-editor-remove"
                onClick={() => removeItem(index)}
                aria-label={`Remove ${label} ${index + 1}`}
              >
                ×
              </button>
            </div>
          </li>
        ))}
      </ul>
      <button
        type="button"
        className="bill-editor-add"
        onClick={() => onChange([...items, { name: "" }])}
      >
        {addLabel || `+ Add ${label.toLowerCase()}`}
      </button>
    </div>
  );
}

function SymptomList({ symptoms, onChange }) {
  const updateSymptom = (index, field, value) => {
    onChange(
      symptoms.map((entry, entryIndex) =>
        entryIndex === index ? { ...entry, [field]: value } : entry
      )
    );
  };

  return (
    <div className="extraction-editor-section">
      <h4>Symptoms</h4>
      <ul className="bill-editor-list">
        {symptoms.map((item, index) => (
          <li key={`symptom-${index}`} className="bill-editor-row">
            <div className="bill-editor-row-grid clinical-symptom-grid">
              <label className="bill-editor-field">
                <span>Symptom</span>
                <input
                  type="text"
                  value={item.name || ""}
                  onChange={(event) => updateSymptom(index, "name", event.target.value)}
                />
              </label>
              <label className="bill-editor-field">
                <span>Duration</span>
                <input
                  type="text"
                  value={item.duration || ""}
                  onChange={(event) =>
                    updateSymptom(index, "duration", event.target.value)
                  }
                />
              </label>
              <button
                type="button"
                className="bill-editor-remove"
                onClick={() =>
                  onChange(symptoms.filter((_, entryIndex) => entryIndex !== index))
                }
                aria-label={`Remove symptom ${index + 1}`}
              >
                ×
              </button>
            </div>
          </li>
        ))}
      </ul>
      <button
        type="button"
        className="bill-editor-add"
        onClick={() =>
          onChange([...symptoms, { name: "", duration: "", severity: "" }])
        }
      >
        + Add symptom
      </button>
    </div>
  );
}

function TestResultList({ testResults, onChange }) {
  const updateResult = (index, field, value) => {
    onChange(
      testResults.map((entry, entryIndex) =>
        entryIndex === index ? { ...entry, [field]: value } : entry
      )
    );
  };

  return (
    <div className="extraction-editor-section">
      <h4>Test results</h4>
      <ul className="bill-editor-list">
        {testResults.map((item, index) => (
          <li key={`test-${index}`} className="bill-editor-row">
            <div className="bill-editor-row-grid">
              <label className="bill-editor-field">
                <span>Test</span>
                <input
                  type="text"
                  value={item.test_name || ""}
                  onChange={(event) =>
                    updateResult(index, "test_name", event.target.value)
                  }
                />
              </label>
              <label className="bill-editor-field">
                <span>Value</span>
                <input
                  type="text"
                  value={item.value || ""}
                  onChange={(event) => updateResult(index, "value", event.target.value)}
                />
              </label>
              <label className="bill-editor-field">
                <span>Unit</span>
                <input
                  type="text"
                  value={item.unit || ""}
                  onChange={(event) => updateResult(index, "unit", event.target.value)}
                />
              </label>
              <button
                type="button"
                className="bill-editor-remove"
                onClick={() =>
                  onChange(testResults.filter((_, entryIndex) => entryIndex !== index))
                }
                aria-label={`Remove test result ${index + 1}`}
              >
                ×
              </button>
            </div>
          </li>
        ))}
      </ul>
      <button
        type="button"
        className="bill-editor-add"
        onClick={() =>
          onChange([
            ...testResults,
            {
              test_name: "",
              value: "",
              unit: "",
              result: "",
              reference_range: "",
            },
          ])
        }
      >
        + Add test result
      </button>
    </div>
  );
}

function BillLineItemsEditor({ lineItems, onChange }) {
  const updateItem = (index, field, value) => {
    onChange(
      lineItems.map((entry, entryIndex) => {
        if (entryIndex !== index) {
          return entry;
        }
        const next = { ...entry, [field]: value };
        if (field === "quantity" || field === "unit_price") {
          const quantity = Math.max(Number(next.quantity) || 0, 0);
          const unitPrice = Math.max(Number(next.unit_price) || 0, 0);
          next.total_price = Math.round(quantity * unitPrice * 100) / 100;
        }
        return next;
      })
    );
  };

  return (
    <div className="extraction-editor-section">
      <h4>Line items</h4>
      <ul className="bill-editor-list">
        {lineItems.map((item, index) => (
          <li key={`line-${index}`} className="bill-editor-row">
            <div className="bill-editor-row-top">
              <label className="bill-editor-field bill-editor-field-grow">
                <span>Item</span>
                <input
                  type="text"
                  value={item.item_name || ""}
                  onChange={(event) =>
                    updateItem(index, "item_name", event.target.value)
                  }
                />
              </label>
              <button
                type="button"
                className="bill-editor-remove"
                onClick={() =>
                  onChange(lineItems.filter((_, entryIndex) => entryIndex !== index))
                }
                aria-label={`Remove line item ${index + 1}`}
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
                  value={item.quantity ?? 1}
                  onChange={(event) =>
                    updateItem(index, "quantity", Number(event.target.value))
                  }
                />
              </label>
              <label className="bill-editor-field">
                <span>Unit price (₹)</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={item.unit_price ?? 0}
                  onChange={(event) =>
                    updateItem(index, "unit_price", Number(event.target.value))
                  }
                />
              </label>
              <label className="bill-editor-field">
                <span>Total (₹)</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={item.total_price ?? 0}
                  onChange={(event) =>
                    updateItem(index, "total_price", Number(event.target.value))
                  }
                />
              </label>
              <label className="bill-editor-field">
                <span>Category</span>
                <select
                  value={item.category || "other"}
                  onChange={(event) =>
                    updateItem(index, "category", event.target.value)
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
        onClick={() =>
          onChange([
            ...lineItems,
            {
              item_name: "",
              quantity: 1,
              unit_price: 0,
              total_price: 0,
              category: "other",
            },
          ])
        }
      >
        + Add line item
      </button>
    </div>
  );
}

function PreauthItemsEditor({ items, onChange }) {
  const updateItem = (index, field, value) => {
    onChange(
      items.map((entry, entryIndex) =>
        entryIndex === index ? { ...entry, [field]: value } : entry
      )
    );
  };

  return (
    <div className="extraction-editor-section">
      <h4>Approved items</h4>
      <ul className="bill-editor-list">
        {items.map((item, index) => (
          <li key={`preauth-${index}`} className="bill-editor-row">
            <div className="bill-editor-row-grid">
              <label className="bill-editor-field bill-editor-field-grow">
                <span>Item</span>
                <input
                  type="text"
                  value={item.name || ""}
                  onChange={(event) => updateItem(index, "name", event.target.value)}
                />
              </label>
              <label className="bill-editor-field">
                <span>Amount (₹)</span>
                <input
                  type="text"
                  value={item.approved_amount ?? ""}
                  onChange={(event) =>
                    updateItem(index, "approved_amount", event.target.value)
                  }
                />
              </label>
              <button
                type="button"
                className="bill-editor-remove"
                onClick={() =>
                  onChange(items.filter((_, entryIndex) => entryIndex !== index))
                }
                aria-label={`Remove approved item ${index + 1}`}
              >
                ×
              </button>
            </div>
          </li>
        ))}
      </ul>
      <button
        type="button"
        className="bill-editor-add"
        onClick={() =>
          onChange([...items, { name: "", approved_amount: "", notes: "" }])
        }
      >
        + Add approved item
      </button>
    </div>
  );
}

export default function DocumentExtractedDataEditor({
  editable,
  onChange,
  disabled = false,
}) {
  if (!editable) {
    return null;
  }

  const setField = (field, value) => {
    onChange({ ...editable, [field]: value });
  };

  const documentType = editable.documentType;

  return (
    <div className={`document-extraction-editor document-extraction-${documentType}`}>
      {documentType === "bill" && (
        <>
          <label className="setting-field setting-field-full">
            <span>Hospital name</span>
            <input
              type="text"
              value={editable.hospital_name || ""}
              disabled={disabled}
              onChange={(event) => setField("hospital_name", event.target.value)}
            />
          </label>
          <label className="setting-field">
            <span>Bill date</span>
            <input
              type="date"
              value={editable.bill_date || ""}
              disabled={disabled}
              onChange={(event) => setField("bill_date", event.target.value)}
            />
          </label>
          <BillLineItemsEditor
            lineItems={editable.line_items || []}
            onChange={(line_items) => setField("line_items", line_items)}
          />
        </>
      )}

      {documentType === "prescription" && (
        <>
          <label className="setting-field setting-field-full">
            <span>Diagnosis</span>
            <input
              type="text"
              value={editable.diagnosis || ""}
              disabled={disabled}
              onChange={(event) => setField("diagnosis", event.target.value)}
            />
          </label>
          <label className="setting-field">
            <span>Prescription date</span>
            <input
              type="date"
              value={editable.prescription_date || ""}
              disabled={disabled}
              onChange={(event) => setField("prescription_date", event.target.value)}
            />
          </label>
          <label className="setting-field setting-field-full">
            <span>Prescriber</span>
            <input
              type="text"
              value={editable.prescriber || ""}
              disabled={disabled}
              onChange={(event) => setField("prescriber", event.target.value)}
            />
          </label>
          <NamedItemList
            label="Medicines"
            items={editable.medicines || []}
            onChange={(medicines) => setField("medicines", medicines)}
          />
          <NamedItemList
            label="Tests"
            items={editable.tests || []}
            onChange={(tests) => setField("tests", tests)}
          />
          <NamedItemList
            label="Procedures"
            items={editable.procedures || []}
            onChange={(procedures) => setField("procedures", procedures)}
          />
          <SymptomList
            symptoms={editable.symptoms || []}
            onChange={(symptoms) => setField("symptoms", symptoms)}
          />
          <TestResultList
            testResults={editable.test_results || []}
            onChange={(test_results) => setField("test_results", test_results)}
          />
        </>
      )}

      {documentType === "lab_report" && (
        <>
          <label className="setting-field setting-field-full">
            <span>Lab name</span>
            <input
              type="text"
              value={editable.lab_name || ""}
              disabled={disabled}
              onChange={(event) => setField("lab_name", event.target.value)}
            />
          </label>
          <label className="setting-field">
            <span>Report date</span>
            <input
              type="date"
              value={editable.report_date || ""}
              disabled={disabled}
              onChange={(event) => setField("report_date", event.target.value)}
            />
          </label>
          <SymptomList
            symptoms={editable.symptoms || []}
            onChange={(symptoms) => setField("symptoms", symptoms)}
          />
          <TestResultList
            testResults={editable.test_results || []}
            onChange={(test_results) => setField("test_results", test_results)}
          />
        </>
      )}

      {documentType === "discharge_summary" && (
        <>
          <label className="setting-field setting-field-full">
            <span>Diagnosis</span>
            <input
              type="text"
              value={editable.diagnosis || ""}
              disabled={disabled}
              onChange={(event) => setField("diagnosis", event.target.value)}
            />
          </label>
          <label className="setting-field">
            <span>Discharge date</span>
            <input
              type="date"
              value={editable.discharge_date || ""}
              disabled={disabled}
              onChange={(event) => setField("discharge_date", event.target.value)}
            />
          </label>
          <SymptomList
            symptoms={editable.symptoms || []}
            onChange={(symptoms) => setField("symptoms", symptoms)}
          />
          <TestResultList
            testResults={editable.test_results || []}
            onChange={(test_results) => setField("test_results", test_results)}
          />
          <NamedItemList
            label="Procedures"
            items={editable.procedures || []}
            onChange={(procedures) => setField("procedures", procedures)}
          />
        </>
      )}

      {documentType === "preauth_letter" && (
        <>
          <label className="setting-field setting-field-full">
            <span>Authorization ID</span>
            <input
              type="text"
              value={editable.authorization_id || ""}
              disabled={disabled}
              onChange={(event) => setField("authorization_id", event.target.value)}
            />
          </label>
          <label className="setting-field">
            <span>Authorization date</span>
            <input
              type="date"
              value={editable.authorization_date || ""}
              disabled={disabled}
              onChange={(event) => setField("authorization_date", event.target.value)}
            />
          </label>
          <label className="setting-field setting-field-full">
            <span>Insurer / scheme</span>
            <input
              type="text"
              value={editable.insurer_or_scheme || ""}
              disabled={disabled}
              onChange={(event) => setField("insurer_or_scheme", event.target.value)}
            />
          </label>
          <PreauthItemsEditor
            items={editable.approved_items || []}
            onChange={(approved_items) => setField("approved_items", approved_items)}
          />
        </>
      )}
    </div>
  );
}
