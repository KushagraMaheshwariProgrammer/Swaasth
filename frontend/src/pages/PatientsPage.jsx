import { motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import PatientForm, {
  emptyPatientForm,
  genderLabel,
} from "../components/PatientForm";
import PatientList from "../components/PatientList";
import {
  computeBillSummary,
  formatCurrency,
  getBillPatientName,
} from "../billUtils";
import { resolveScheme } from "../data/schemes";
import { useAuth } from "../context/AuthContext";
import { deleteBill } from "../services/bills";
import {
  createPatient,
  deletePatient,
  getPatient,
  getPatientBills,
  getPatients,
  getPatientsLocalSnapshot,
  updatePatient,
} from "../services/patients";

const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.35 },
};

export default function PatientsPage() {
  const { patientId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [patients, setPatients] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [patientBills, setPatientBills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [billsLoading, setBillsLoading] = useState(false);
  const [syncMessage, setSyncMessage] = useState("");
  const [error, setError] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState(emptyPatientForm());
  const [saving, setSaving] = useState(false);
  const [deletingBillId, setDeletingBillId] = useState(null);
  const [deletingPatientId, setDeletingPatientId] = useState(null);

  const loadPatients = useCallback(async () => {
    if (!user) {
      return;
    }
    setError("");
    const localSnapshot = getPatientsLocalSnapshot(user.uid);
    if (localSnapshot.length) {
      setPatients(localSnapshot);
      setLoading(false);
    } else {
      setLoading(true);
    }
    try {
      const list = await getPatients(user.uid);
      setPatients(list);
    } catch (err) {
      setError(err.message || "Unable to load patients.");
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (!user || patientId) {
      return;
    }
    loadPatients();
  }, [user, patientId, loadPatients]);

  useEffect(() => {
    let cancelled = false;

    const loadDetail = async () => {
      if (!user || !patientId) {
        setSelectedPatient(null);
        setPatientBills([]);
        return;
      }
      setBillsLoading(true);
      setError("");
      setSyncMessage("");

      const localPatient = getPatientsLocalSnapshot(user.uid).find(
        (entry) => entry.id === patientId || entry.localId === patientId
      );
      if (localPatient) {
        setSelectedPatient(localPatient);
        setForm({
          name: localPatient.name || "",
          age: localPatient.age != null ? String(localPatient.age) : "",
          gender: localPatient.gender || "",
          state: localPatient.state || "",
          ayushmanEligible: Boolean(localPatient.ayushmanEligible),
          aarogyaBhadrathaEligible: Boolean(
            localPatient.aarogyaBhadrathaEligible
          ),
          savePastBills: Boolean(localPatient.savePastBills),
        });
      } else {
        setLoading(true);
      }

      try {
        const [patient, bills] = await Promise.all([
          getPatient(user.uid, patientId),
          getPatientBills(user.uid, patientId),
        ]);
        if (cancelled) {
          return;
        }
        if (!patient) {
          setError("Patient not found.");
          setSelectedPatient(null);
          setPatientBills([]);
          return;
        }
        setSelectedPatient(patient);
        setForm({
          name: patient.name || "",
          age: patient.age != null ? String(patient.age) : "",
          gender: patient.gender || "",
          state: patient.state || "",
          ayushmanEligible: Boolean(patient.ayushmanEligible),
          aarogyaBhadrathaEligible: Boolean(patient.aarogyaBhadrathaEligible),
          savePastBills: Boolean(patient.savePastBills),
        });
        setPatientBills(bills);
        const pendingLocal = bills.filter((bill) => bill.localOnly).length;
        if (pendingLocal > 0) {
          setSyncMessage(
            `${pendingLocal} bill${pendingLocal === 1 ? "" : "s"} on this device — syncing with your account.`
          );
        } else if (bills.length > 0) {
          setSyncMessage(
            `${bills.length} past bill${bills.length === 1 ? "" : "s"} loaded from your account.`
          );
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Unable to load patient.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          setBillsLoading(false);
        }
      }
    };

    loadDetail();
    return () => {
      cancelled = true;
    };
  }, [user, patientId]);

  const handleCreate = async (event) => {
    event.preventDefault();
    if (!user?.uid) {
      setError("You must be signed in to save a patient.");
      return;
    }
    setSaving(true);
    setError("");
    setSyncMessage("");
    try {
      const result = await createPatient(user.uid, form);
      const list = await getPatients(user.uid);
      setPatients(list);
      setShowAddForm(false);
      setForm(emptyPatientForm());
      const savedName = result.patient?.name || form.name;
      setSyncMessage(`Patient "${savedName}" saved successfully.`);
    } catch (err) {
      setError(err.message || "Unable to add patient.");
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async (event) => {
    event.preventDefault();
    if (!user || !patientId) {
      return;
    }
    setSaving(true);
    setError("");
    try {
      const result = await updatePatient(user.uid, patientId, form);
      if (result.warning) {
        setSyncMessage(result.warning);
      }
      const updated = await getPatient(user.uid, result.id);
      setSelectedPatient(updated);
      setEditing(false);
      await loadPatients();
    } catch (err) {
      setError(err.message || "Unable to update patient.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteBill = async (bill) => {
    if (!user?.uid || !bill?.id) {
      return;
    }
    const title = bill.filename || "Hospital bill";
    if (
      !window.confirm(
        `Permanently delete this bill?\n\n${title}\nBill ID: ${bill.id}\n\nThis action cannot be undone.`
      )
    ) {
      return;
    }
    setDeletingBillId(bill.id);
    setError("");
    try {
      await deleteBill(user.uid, bill.id);
      setPatientBills((prev) => prev.filter((entry) => entry.id !== bill.id));
    } catch (err) {
      setError(err.message || "Unable to delete bill.");
    } finally {
      setDeletingBillId(null);
    }
  };

  const confirmDeletePatient = (patient, billCount = 0) => {
    const patientName = patient?.name || "this patient";
    const id = patient?.id || patientId;
    const billWarning =
      billCount > 0
        ? `\n\nAll ${billCount} medical bill${billCount === 1 ? "" : "s"} linked to this patient will also be permanently deleted from Past bills.`
        : "\n\nAll medical bills linked to this patient will also be permanently deleted.";
    return window.confirm(
      `Permanently delete patient "${patientName}"?\n\nPatient ID: ${id}${billWarning}\n\nThis action cannot be undone.`
    );
  };

  const handleDeletePatient = async (patient, { billCount = 0, redirect = false } = {}) => {
    if (!user?.uid || !patient?.id) {
      return;
    }
    if (!confirmDeletePatient(patient, billCount)) {
      return;
    }

    const patientName = patient.name || "Patient";
    setDeletingPatientId(patient.id);
    setError("");
    setSyncMessage("");
    try {
      await deletePatient(user.uid, patient.id);
      if (redirect) {
        navigate("/patients");
      }
      await loadPatients();
      setSyncMessage(`Patient "${patientName}" deleted.`);
    } catch (err) {
      setError(err.message || "Unable to delete patient.");
    } finally {
      setDeletingPatientId(null);
    }
  };

  const handleDelete = () =>
    handleDeletePatient(selectedPatient, {
      billCount: patientBills.length,
      redirect: true,
    });

  return (
    <motion.div className="check-page" {...pageTransition}>
      <main className="check-wrap patients-wrap">
        <div className="check-topbar">
          <Link
            to={patientId ? "/patients" : "/"}
            className="back-link"
          >
            ← {patientId ? "All patients" : "Back"}
          </Link>
          <div className="user-nav">
            <Link to="/check" className="user-nav-link">
              Check bill
            </Link>
            <Link to="/history" className="user-nav-link">
              Past bills
            </Link>
          </div>
        </div>

        {!patientId ? (
          <>
            <header className="check-header">
              <h1>Your patients</h1>
              <p>Add family members to track bills and Ayushman Bharat eligibility.</p>
            </header>

            {!showAddForm && (
              <button
                type="button"
                className="analyze-btn patients-add-btn"
                onClick={() => {
                  setForm(emptyPatientForm());
                  setShowAddForm(true);
                  setError("");
                }}
              >
                Add patients
              </button>
            )}

            {showAddForm && (
              <section className="patient-card-shell">
                <h2>New patient</h2>
                <PatientForm
                  form={form}
                  setForm={setForm}
                  onSubmit={handleCreate}
                  onCancel={() => {
                    setShowAddForm(false);
                    setForm(emptyPatientForm());
                  }}
                  submitLabel="Save patient"
                  saving={saving}
                  error={error}
                />
              </section>
            )}

            {loading && <p className="auth-info">Loading patients...</p>}
            {error && !showAddForm && <p className="error-text">{error}</p>}

            {syncMessage && !showAddForm && (
              <p className="auth-info patient-save-success">{syncMessage}</p>
            )}

            {!loading && !patients.length && !showAddForm && !syncMessage && (
              <p className="auth-info">
                No patients yet. Tap &quot;Add patients&quot; to create a profile.
              </p>
            )}

            <PatientList
              patients={patients}
              mode="link"
              onDelete={(patient) => handleDeletePatient(patient)}
              deletingId={deletingPatientId}
            />
          </>
        ) : (
          <>
            {loading && !selectedPatient && (
              <p className="auth-info">Loading patient...</p>
            )}
            {selectedPatient && (
              <>
                <header className="check-header patient-detail-header">
                  <div>
                    <h1>{selectedPatient.name}</h1>
                    <p>
                      {selectedPatient.age} yrs · {genderLabel(selectedPatient.gender)}
                      {selectedPatient.ayushmanEligible && (
                        <> · Ayushman Bharat PM-JAY eligible</>
                      )}
                    </p>
                  </div>
                  <div className="patient-detail-actions">
                    <Link
                      to="/check"
                      state={{ patientId: selectedPatient.id }}
                      className="analyze-btn patient-check-link"
                    >
                      Check bill for this patient
                    </Link>
                    {!editing && (
                      <>
                        <button
                          type="button"
                          className="bill-editor-secondary"
                          onClick={() => setEditing(true)}
                        >
                          Edit profile
                        </button>
                        <button
                          type="button"
                          className="bill-editor-secondary patient-delete-action"
                          disabled={Boolean(deletingPatientId)}
                          onClick={handleDelete}
                        >
                          {deletingPatientId ? "Deleting…" : "Delete patient"}
                        </button>
                      </>
                    )}
                  </div>
                </header>

                {editing ? (
                  <section className="patient-card-shell">
                    <h2>Edit patient</h2>
                    <PatientForm
                      form={form}
                      setForm={setForm}
                      onSubmit={handleUpdate}
                      onCancel={() => {
                        setEditing(false);
                        setForm({
                          name: selectedPatient.name || "",
                          age:
                            selectedPatient.age != null
                              ? String(selectedPatient.age)
                              : "",
                          gender: selectedPatient.gender || "",
                          state: selectedPatient.state || "",
                          ayushmanEligible: Boolean(
                            selectedPatient.ayushmanEligible
                          ),
                          aarogyaBhadrathaEligible: Boolean(
                            selectedPatient.aarogyaBhadrathaEligible
                          ),
                          savePastBills: Boolean(selectedPatient.savePastBills),
                        });
                      }}
                      submitLabel="Save changes"
                      saving={saving}
                      error={error}
                    />
                  </section>
                ) : null}

                {syncMessage && <p className="auth-info">{syncMessage}</p>}

                <section className="patient-bills-section">
                  <h2>Past bills for this patient</h2>
                  {billsLoading && (
                    <p className="auth-info">Syncing bills from your account...</p>
                  )}
                  {!billsLoading && !patientBills.length && (
                    <p className="auth-info">
                      No bills linked to this patient yet. Upload a bill from Check
                      bill and select this patient.
                    </p>
                  )}
                  <ul className="history-list">
                    {patientBills.map((bill) => {
                      const summary = computeBillSummary(bill);
                      const patientName =
                        getBillPatientName(bill) || selectedPatient.name;
                      const title = bill.filename || "Hospital bill";
                      const isDeleting = deletingBillId === bill.id;
                      return (
                        <li key={bill.id} className="history-list-row">
                          <Link
                            to={`/history/${bill.id}`}
                            className="history-list-item history-list-item-flex"
                          >
                            <div>
                              <strong>{title}</strong>
                              <p>
                                {patientName && (
                                  <>
                                    Patient: <strong>{patientName}</strong>
                                    {" · "}
                                  </>
                                )}
                                {bill.comparison_settings?.city &&
                                  `${bill.comparison_settings.city} · `}
                                {resolveScheme(bill).label}
                              </p>
                            </div>
                            <div className="history-list-meta">
                              <span className="history-overcharge">
                                {formatCurrency(summary.totalOvercharged)} over
                              </span>
                            </div>
                          </Link>
                          <button
                            type="button"
                            className="history-delete-btn"
                            disabled={isDeleting}
                            aria-label={`Delete bill ${title}`}
                            onClick={() => handleDeleteBill(bill)}
                          >
                            {isDeleting ? "Deleting…" : "Delete"}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </section>

              </>
            )}
            {error && (!selectedPatient || !editing) && (
              <p className="error-text">{error}</p>
            )}
          </>
        )}
      </main>
    </motion.div>
  );
}
