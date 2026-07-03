import { formatHospitalLocation } from "../lib/hospitalDisplay";

export function formatHospitalLabel(hospital) {
  if (!hospital) {
    return "";
  }
  const location = formatHospitalLocation(hospital.city, "", hospital.state);
  const name = hospital.name || "Unnamed hospital";
  return location ? `${name} · ${location}` : name;
}

export default function HospitalList({
  hospitals,
  selectedId = "",
  onSelect,
  onDelete,
  deletingId = "",
  mode = "select",
}) {
  if (!hospitals.length) {
    return null;
  }

  return (
    <ul className="patients-list hospitals-list">
      {hospitals.map((hospital) => {
        const isSelected = selectedId === hospital.id;
        const isDeleting = deletingId === hospital.id;
        const content = (
          <div>
            <strong>{hospital.name || "Unnamed hospital"}</strong>
            <p>
              {formatHospitalLocation(hospital.city, "", hospital.state) || "—"}
            </p>
          </div>
        );

        if (mode === "select") {
          return (
            <li key={hospital.id}>
              <button
                type="button"
                className={`patient-list-card patient-list-card-selectable${
                  isSelected ? " is-selected" : ""
                }`}
                aria-pressed={isSelected}
                onClick={() => onSelect?.(hospital.id)}
              >
                {content}
              </button>
            </li>
          );
        }

        if (onDelete) {
          return (
            <li key={hospital.id} className="history-list-row">
              <div className="patient-list-card hospital-list-card-static">
                {content}
              </div>
              <button
                type="button"
                className="history-delete-btn"
                disabled={isDeleting}
                aria-label={`Delete hospital ${hospital.name || "profile"}`}
                onClick={() => onDelete(hospital)}
              >
                {isDeleting ? "Deleting…" : "Delete"}
              </button>
            </li>
          );
        }

        return (
          <li key={hospital.id}>
            <div className="patient-list-card hospital-list-card-static">{content}</div>
          </li>
        );
      })}
    </ul>
  );
}
