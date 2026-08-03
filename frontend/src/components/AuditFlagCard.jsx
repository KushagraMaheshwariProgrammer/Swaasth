import { useState } from "react";
import {
  flagDisplayLabel,
  getAuditConfidenceMeta,
} from "../auditAdvocacyUtils";
import { getAuditSeverityMeta } from "../billUtils";
import { POSSIBLE_ISSUE_NOTICE } from "../data/hedgingCopy";
import LegalPathwayModal from "./LegalPathwayModal";
import StgCitationModal from "./StgCitationModal";

const OVERCHARGE_FLAG_TYPES = new Set([
  "MEDICINE_PRICE_DISCREPANCY",
  "PACKAGE_COMPONENT_CHARGED_SEPARATELY",
  "PREAUTH_AMOUNT_ABOVE_APPROVED",
]);

const CLINICAL_CATEGORIES = new Set(["diagnosis", "investigation", "prescription"]);

function isClinicalFlag(flag) {
  return CLINICAL_CATEGORIES.has(flag?.category || "");
}

function getDisplayConfidenceMeta(flag) {
  if (
    isClinicalFlag(flag) &&
    flag?.confidence === "HIGH" &&
    flag?.citation_verified !== true
  ) {
    return {
      ...getAuditConfidenceMeta("MEDIUM"),
      label: "Verify with doctor",
      hint:
        "This clinical point was not backed by a verified STG citation in the retrieved excerpts.",
    };
  }
  return getAuditConfidenceMeta(flag.confidence);
}

function stgReferenceParts(reference) {
  if (!reference || typeof reference !== "object") {
    return [];
  }
  return [
    reference.condition,
    reference.section,
    reference.page ? `p. ${reference.page}` : "",
  ].filter(Boolean);
}

function sourceLabel(flag) {
  const citation = flag?.stg_citation;
  if (citation?.source?.corpus_label) {
    return citation.source.corpus_label;
  }
  return null;
}

export default function AuditFlagCard({ flag, index }) {
  const [showStg, setShowStg] = useState(false);
  const [showLegal, setShowLegal] = useState(false);

  const severityMeta = getAuditSeverityMeta(flag.severity);
  const confidenceMeta = getDisplayConfidenceMeta(flag);
  const typeLabel = flag.display_label || flagDisplayLabel(flag.type);
  const referenceParts = stgReferenceParts(flag.stg_reference);
  const corpusLabel = sourceLabel(flag);
  const flagTitle = flag.item ? `${typeLabel}: ${flag.item}` : typeLabel;
  const hasStg = Boolean(flag?.stg_citation?.full_text);
  const hasLegal = Boolean(flag?.legal_pathway);
  const isOverchargeRelated = OVERCHARGE_FLAG_TYPES.has(String(flag?.type || ""));

  return (
    <>
      <article
        key={`${flag.type || "flag"}-${flag.item || "item"}-${index}`}
        className={severityMeta.cardClass}
      >
        <div className="result-top">
          <h4>{flag.item || "--"}</h4>
          <span className={confidenceMeta.badgeClass}>{confidenceMeta.label}</span>
        </div>
        <p className="audit-confidence-hint">{confidenceMeta.hint}</p>
        <p className="audit-flag-type">{typeLabel}</p>
        {isOverchargeRelated && (
          <p className="treatment-audit-disclaimer">{POSSIBLE_ISSUE_NOTICE}</p>
        )}
        <p className="audit-flag-reason">{flag.reason}</p>
        {corpusLabel && (
          <p className="audit-flag-source-chip">
            Guideline corpus: <strong>{corpusLabel}</strong>
          </p>
        )}
        {referenceParts.length > 0 && (
          <p className="audit-flag-reference-chip">
            STG reference: <strong>{referenceParts.join(" · ")}</strong>
          </p>
        )}
        {flag.guideline_basis && (
          <p className="audit-flag-reference">
            <strong>Why this matters:</strong> {flag.guideline_basis}
          </p>
        )}
        {flag.legal_pathway?.broader_concept && (
          <p className="audit-flag-legal-hint">
            <strong>Educational legal concept:</strong>{" "}
            {flag.legal_pathway.broader_concept}
          </p>
        )}
        <p className="audit-flag-recommendation">
          <strong>Suggested question:</strong> {flag.recommendation}
        </p>
        {(hasStg || hasLegal) && (
          <div className="audit-flag-actions">
            {hasStg && (
              <button
                type="button"
                className="bill-editor-secondary audit-flag-action-btn"
                onClick={() => setShowStg(true)}
              >
                View full STG paragraph
              </button>
            )}
            {hasLegal && (
              <button
                type="button"
                className="bill-editor-secondary audit-flag-action-btn"
                onClick={() => setShowLegal(true)}
              >
                View possible legal pathway
              </button>
            )}
          </div>
        )}
      </article>

      {showStg && (
        <StgCitationModal
          citation={flag.stg_citation}
          flagLabel={flagTitle}
          onClose={() => setShowStg(false)}
        />
      )}
      {showLegal && (
        <LegalPathwayModal
          pathway={flag.legal_pathway}
          flagLabel={flagTitle}
          onClose={() => setShowLegal(false)}
        />
      )}
    </>
  );
}
