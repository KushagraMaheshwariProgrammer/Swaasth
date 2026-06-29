import { Link } from "react-router-dom";
import { genderLabel } from "./PatientForm";

export default function PatientList({
  patients,
  selectedId = "",
  onSelect,
  onDelete,
  deletingId = "",
  mode = "link",
}) {
  if (!patients.length) {
    return null;
  }

  return (
    <ul className="patients-list">
      {patients.map((patient) => {
        const isSelected = selectedId === patient.id;
        const isDeleting = deletingId === patient.id;
        const content = (
          <>
            <div>
              <strong>{patient.name || "Unnamed patient"}</strong>
              <p>
                {patient.age != null ? `${patient.age} yrs` : "—"} ·{" "}
                {genderLabel(patient.gender)}
              </p>
            </div>
          </>
        );

        if (mode === "select") {
          return (
            <li key={patient.id}>
              <button
                type="button"
                className={`patient-list-card patient-list-card-selectable${
                  isSelected ? " is-selected" : ""
                }`}
                aria-pressed={isSelected}
                onClick={() => onSelect?.(patient.id)}
              >
                {content}
              </button>
            </li>
          );
        }

        if (onDelete) {
          return (
            <li key={patient.id} className="history-list-row">
              <Link to={`/patients/${patient.id}`} className="patient-list-card">
                {content}
              </Link>
              <button
                type="button"
                className="history-delete-btn"
                disabled={isDeleting}
                aria-label={`Delete patient ${patient.name || "profile"}`}
                onClick={() => onDelete(patient)}
              >
                {isDeleting ? "Deleting…" : "Delete"}
              </button>
            </li>
          );
        }

        return (
          <li key={patient.id}>
            <Link to={`/patients/${patient.id}`} className="patient-list-card">
              {content}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
