import {
  formatDisplayName,
  formatEmpanelmentStatusLabel,
  formatHospitalLocation,
  formatHospitalTypeBadge,
} from "../lib/hospitalDisplay";
import { formatSpecialitiesForDisplay } from "../lib/pmjaySpecialities";

function statusBadgeClass(status) {
  const text = String(status || "").toLowerCase();
  if (text === "empanelled" || text === "active") {
    return "pmjay-status-badge pmjay-status-success";
  }
  if (text === "suspended" || text === "delisted") {
    return "pmjay-status-badge pmjay-status-warning";
  }
  if (text === "not_found" || text.includes("not found")) {
    return "pmjay-status-badge pmjay-status-muted";
  }
  if (text.includes("manual")) {
    return "pmjay-status-badge pmjay-status-info";
  }
  return "pmjay-status-badge";
}

function statusLabel(status) {
  const text = String(status || "").replaceAll("_", " ");
  if (!text) {
    return "Unknown";
  }
  return text.replace(/\b\w/g, (char) => char.toUpperCase());
}

function confidenceLabel(value) {
  if (value === null || value === undefined) {
    return "—";
  }
  return `${Math.round(Number(value) * 100)}%`;
}

export default function PmjayHospitalVerificationReport({ verification }) {
  if (!verification?.selected) {
    return null;
  }

  const advisories = verification.advisories || [];
  const candidates = verification.candidates || [];
  const location = formatHospitalLocation(
    verification.city,
    verification.district,
    verification.state
  );
  const specialities = formatSpecialitiesForDisplay(verification.specialities);

  return (
    <section
      className="scheme-advisory pmjay-hospital-verification"
      aria-label="PM-JAY hospital empanelment check"
    >
      <div className="scheme-advisory-header">
        <div className="pmjay-hospital-verification-heading">
          <h3>PM-JAY Hospital Empanelment Check</h3>
          <p className="scheme-advisory-description">
            Hospital empanelment advisory based on the PM-JAY directory loaded in
            the app. This does not replace official PM-JAY verification.
          </p>
        </div>
        <span className={statusBadgeClass(verification.status)}>
          {statusLabel(verification.status)}
        </span>
      </div>

      <div className="pmjay-hospital-verification-card">
        <ul className="pmjay-meta-list">
          <li>
            Hospital on bill:{" "}
            <strong>{formatDisplayName(verification.ocr_hospital_name) || "—"}</strong>
          </li>
          <li>
            Matched PM-JAY hospital:{" "}
            <strong>
              {formatDisplayName(verification.matched_hospital_name) || "—"}
            </strong>
          </li>
          <li>Match confidence: {confidenceLabel(verification.confidence_score)}</li>
          <li>Location: {location || "—"}</li>
          <li>
            Hospital type:{" "}
            {formatHospitalTypeBadge(verification.hospital_type) || "—"}
          </li>
          <li>Empanelment type: {verification.empanelment_type || "—"}</li>
          <li>
            Empanelment status:{" "}
            {formatEmpanelmentStatusLabel(verification.empanelment_status) || "—"}
          </li>
          {specialities.hasSpecialities && (
            <li>
              Specialities:{" "}
              {specialities.detailsText ||
                specialities.cardLine ||
                "Available — verify with hospital/helpdesk"}
            </li>
          )}
          {verification.match_reason && (
            <li className="pmjay-match-reason">
              Match reason: {verification.match_reason}
            </li>
          )}
        </ul>
      </div>

      {candidates.length > 0 && (
        <div className="pmjay-hospital-verification-card">
          <h4>Closest matches</h4>
          <ul className="pmjay-candidate-list">
            {candidates.map((candidate) => (
              <li key={`${candidate.hospital_id}-${candidate.hospital_name}`}>
                <strong>{formatDisplayName(candidate.hospital_name)}</strong>
                {" · "}
                {formatHospitalLocation(
                  candidate.city,
                  candidate.district,
                  candidate.state
                ) || "—"}
                {candidate.confidence_score != null && (
                  <> · {confidenceLabel(candidate.confidence_score)}</>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {advisories.length > 0 && (
        <div className="cghs-eligibility-preview-box pmjay-advisory-box">
          {advisories.map((message) => (
            <p key={message}>{message}</p>
          ))}
        </div>
      )}
    </section>
  );
}
