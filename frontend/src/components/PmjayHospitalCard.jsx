import { useState } from "react";
import {
  empanelmentStatusBadgeClass,
  formatDisplayName,
  formatEmpanelmentStatusLabel,
  formatHospitalLocation,
  formatHospitalTypeBadge,
  hospitalTypeBadgeClass,
} from "../lib/hospitalDisplay";
import { formatSpecialitiesForDisplay } from "../lib/pmjaySpecialities";

export default function PmjayHospitalCard({ hospital }) {
  const [expanded, setExpanded] = useState(false);
  const location = formatHospitalLocation(
    hospital.city,
    hospital.district,
    hospital.state
  );
  const specialities = formatSpecialitiesForDisplay(hospital.specialities);
  const hospitalName = formatDisplayName(hospital.hospital_name);
  const typeLabel = formatHospitalTypeBadge(hospital.hospital_type);
  const statusLabel = formatEmpanelmentStatusLabel(hospital.empanelment_status);

  return (
    <article className="pmjay-hospital-card-v2">
      <div className="pmjay-hospital-card-v2-top">
        <div className="pmjay-hospital-card-v2-main">
          <h3 className="pmjay-hospital-card-v2-name">{hospitalName}</h3>
          {location ? (
            <p className="pmjay-hospital-card-v2-location">{location}</p>
          ) : null}
        </div>
        <div className="pmjay-hospital-card-v2-badges">
          <span className={hospitalTypeBadgeClass(hospital.hospital_type)}>
            {typeLabel}
          </span>
          <span className={empanelmentStatusBadgeClass(hospital.empanelment_status)}>
            {statusLabel}
          </span>
        </div>
      </div>

      {specialities.hasSpecialities && specialities.cardLine ? (
        <p className="pmjay-hospital-card-v2-specialities">{specialities.cardLine}</p>
      ) : null}

      {specialities.chips.length > 0 && (
        <div className="pmjay-hospital-card-v2-chips" aria-label="Speciality highlights">
          {specialities.chips.map((chip) => (
            <span key={chip} className="pmjay-speciality-chip">
              {chip}
            </span>
          ))}
        </div>
      )}

      {(specialities.allReadable.length > 2 || specialities.detailsText) && (
        <button
          type="button"
          className="eligibility-learn-btn pmjay-hospital-card-v2-details-btn"
          onClick={() => setExpanded((prev) => !prev)}
          aria-expanded={expanded}
        >
          {expanded ? "Hide details" : "View details"}
        </button>
      )}

      {expanded && specialities.detailsText && (
        <div className="pmjay-hospital-card-v2-details">
          <p className="pmjay-hospital-card-v2-details-label">Specialities</p>
          {specialities.allReadable.length > 0 ? (
            <ul className="pmjay-hospital-card-v2-details-list">
              {specialities.allReadable.map((name) => (
                <li key={name}>{name}</li>
              ))}
            </ul>
          ) : (
            <p>{specialities.detailsText}</p>
          )}
        </div>
      )}
    </article>
  );
}
