import { useEffect, useState } from "react";
import LocationSearchPicker from "./LocationSearchPicker";
import HospitalList from "./HospitalList";
import { getCities, getStateOptions } from "../services/locations";
import {
  createHospital,
  deleteHospital,
  getLocalHospitalsSnapshot,
  getPatientHospitals,
} from "../services/patientHospitals";

const emptyHospitalForm = () => ({
  name: "",
  state: "",
  city: "",
});

export default function PatientHospitalsSection({
  userId,
  patientId,
  onHospitalsChange,
  disabled = false,
}) {
  const [hospitals, setHospitals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [form, setForm] = useState(emptyHospitalForm());
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const states = getStateOptions();
  const cities = getCities(form.state);

  const loadHospitals = async () => {
    if (!userId || !patientId) {
      setHospitals([]);
      setLoading(false);
      return;
    }
    const localSnapshot = getLocalHospitalsSnapshot(userId, patientId);
    if (localSnapshot.length) {
      setHospitals(localSnapshot);
      setLoading(false);
    } else {
      setLoading(true);
    }
    try {
      const list = await getPatientHospitals(userId, patientId);
      setHospitals(list);
      onHospitalsChange?.(list);
    } catch (err) {
      setError(err.message || "Unable to load hospitals.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHospitals();
  }, [userId, patientId]);

  const handleCreate = async (event) => {
    event.preventDefault();
    if (!userId || !patientId) {
      return;
    }
    setSaving(true);
    setError("");
    setInfo("");
    try {
      const saved = await createHospital(userId, patientId, form);
      const next = await getPatientHospitals(userId, patientId);
      setHospitals(next);
      onHospitalsChange?.(next);
      setForm(emptyHospitalForm());
      setShowAddForm(false);
      setInfo(`Hospital "${saved.name}" saved.`);
    } catch (err) {
      setError(err.message || "Unable to save hospital.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (hospital) => {
    if (!hospital?.id) {
      return;
    }
    if (
      !window.confirm(
        `Delete hospital "${hospital.name}"?\n\nDocuments linked to this hospital will keep their saved data, but you will need to set up the hospital again for new uploads.`
      )
    ) {
      return;
    }
    setDeletingId(hospital.id);
    setError("");
    try {
      await deleteHospital(userId, patientId, hospital.id);
      const next = await getPatientHospitals(userId, patientId);
      setHospitals(next);
      onHospitalsChange?.(next);
    } catch (err) {
      setError(err.message || "Unable to delete hospital.");
    } finally {
      setDeletingId("");
    }
  };

  return (
    <section className="patient-hospitals-section">
      <h2>Hospitals</h2>
      <p className="clinical-history-hint">
        Add each hospital where this patient has received care. You must select a
        hospital before uploading documents.
      </p>

      {loading && <p className="auth-info">Loading hospitals...</p>}

      {!loading && !showAddForm && (
        <button
          type="button"
          className="analyze-btn patients-add-btn"
          onClick={() => {
            setForm(emptyHospitalForm());
            setShowAddForm(true);
            setError("");
            setInfo("");
          }}
          disabled={disabled}
        >
          Add hospital
        </button>
      )}

      {showAddForm && (
        <form className="patient-card-shell hospital-form" onSubmit={handleCreate}>
          <h3>New hospital</h3>
          <label className="setting-field setting-field-full">
            <span>Hospital name</span>
            <input
              type="text"
              value={form.name}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, name: event.target.value }))
              }
              placeholder="e.g. City General Hospital"
              disabled={disabled || saving}
              required
            />
          </label>
          <div className="comparison-settings-grid">
            <LocationSearchPicker
              label="State/UT"
              items={states}
              value={form.state}
              onSelect={(value) =>
                setForm((prev) => ({ ...prev, state: value, city: "" }))
              }
              disabled={disabled || saving}
              placeholder="Select state/UT"
              emptyLabel="No states available"
            />
            <LocationSearchPicker
              label="City"
              items={cities}
              value={form.city}
              onSelect={(value) => setForm((prev) => ({ ...prev, city: value }))}
              disabled={disabled || saving || !form.state}
              placeholder="Select city"
              emptyLabel={form.state ? "No cities available" : "Select state/UT first"}
            />
          </div>
          <div className="patient-medical-history-actions">
            <button
              type="submit"
              className="analyze-btn"
              disabled={disabled || saving}
            >
              {saving ? "Saving..." : "Save hospital"}
            </button>
            <button
              type="button"
              className="bill-editor-secondary"
              onClick={() => {
                setShowAddForm(false);
                setForm(emptyHospitalForm());
                setError("");
              }}
              disabled={saving}
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {info && <p className="auth-info patient-save-success">{info}</p>}
      {error && <p className="error-text">{error}</p>}

      {!loading && !hospitals.length && !showAddForm && (
        <p className="clinical-history-empty">
          No hospitals yet. Add a hospital to upload documents for this patient.
        </p>
      )}

      <HospitalList
        hospitals={hospitals}
        mode="manage"
        onDelete={handleDelete}
        deletingId={deletingId}
      />
    </section>
  );
}
