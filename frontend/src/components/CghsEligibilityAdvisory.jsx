import { useState } from "react";
import {
  CGHS_FALLBACK_NOTE,
  CGHS_IMPORTANT_NOTE,
  getCghsEligibilityDisplayMode,
} from "../data/cghsEligibilityCriteria";
import CghsEligibilityCriteriaContent from "./CghsEligibilityCriteriaContent";

export default function CghsEligibilityAdvisory({ advisory, report }) {
  const displayMode = report ? getCghsEligibilityDisplayMode(report) : null;
  const resolvedAdvisory =
    advisory ||
    (displayMode?.show ? report?.cghs_eligibility_advisory : null);

  if (!resolvedAdvisory && !displayMode?.show) {
    return null;
  }

  const data = resolvedAdvisory || {};
  const mode = data.mode || displayMode?.mode || "full";
  const isFallback = mode === "fallback";
  const [criteriaExpanded, setCriteriaExpanded] = useState(!isFallback);

  const title = data.title || "CGHS Eligibility Criteria";
  const subtitle = data.subtitle;
  const badge = data.badge || "Eligibility Advisory";
  const residenceRule = data.residence_rule;
  const groups = data.groups;
  const importantNote = data.important_note || CGHS_IMPORTANT_NOTE;
  const fallbackNote = data.fallback_note || CGHS_FALLBACK_NOTE;
  const previewMessages = data.eligibility_preview || [];

  return (
    <section
      className="scheme-advisory cghs-eligibility-advisory"
      aria-label="CGHS eligibility advisory"
    >
      <div className="scheme-advisory-header">
        <div className="cghs-eligibility-advisory-heading">
          <h3>{title}</h3>
          {subtitle && <p className="scheme-advisory-description">{subtitle}</p>}
        </div>
        <span className="scheme-advisory-badge">{badge}</span>
      </div>

      {isFallback && (
        <p className="cghs-eligibility-fallback-note">{fallbackNote}</p>
      )}

      {previewMessages.length > 0 && (
        <div className="cghs-eligibility-preview-box">
          {previewMessages.map((message) => (
            <p key={message}>{message}</p>
          ))}
        </div>
      )}

      {isFallback ? (
        <div className="cghs-eligibility-collapsed-wrap">
          <button
            type="button"
            className="eligibility-learn-btn cghs-eligibility-expand-btn"
            onClick={() => setCriteriaExpanded((prev) => !prev)}
            aria-expanded={criteriaExpanded}
          >
            {criteriaExpanded
              ? "Hide CGHS eligibility criteria"
              : "View CGHS eligibility criteria"}
          </button>
          {criteriaExpanded && (
            <CghsEligibilityCriteriaContent
              groups={groups}
              residenceRule={residenceRule}
              defaultExpanded={false}
            />
          )}
        </div>
      ) : (
        <CghsEligibilityCriteriaContent
          groups={groups}
          residenceRule={residenceRule}
          defaultExpanded={false}
        />
      )}

      <p className="scheme-advisory-note">{importantNote}</p>
    </section>
  );
}
