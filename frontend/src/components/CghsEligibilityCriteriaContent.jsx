import { useState } from "react";
import {
  CGHS_ELIGIBILITY_GROUPS,
  CGHS_RESIDENCE_RULE,
} from "../data/cghsEligibilityCriteria";

export default function CghsEligibilityCriteriaContent({
  groups = CGHS_ELIGIBILITY_GROUPS,
  residenceRule = CGHS_RESIDENCE_RULE,
  defaultExpanded = false,
  compact = false,
}) {
  const [expandedGroups, setExpandedGroups] = useState(() =>
    defaultExpanded ? new Set(groups.map((group) => group.id)) : new Set()
  );

  const toggleGroup = (groupId) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(groupId)) {
        next.delete(groupId);
      } else {
        next.add(groupId);
      }
      return next;
    });
  };

  return (
    <div className={`cghs-eligibility-content${compact ? " cghs-eligibility-content-compact" : ""}`}>
      <div className="cghs-eligibility-residence-rule">
        <p>{residenceRule}</p>
      </div>

      <div className="cghs-eligibility-accordion">
        {groups.map((group) => {
          const isOpen = expandedGroups.has(group.id);
          return (
            <div key={group.id} className="cghs-eligibility-accordion-item">
              <button
                type="button"
                className="cghs-eligibility-accordion-trigger"
                aria-expanded={isOpen}
                onClick={() => toggleGroup(group.id)}
              >
                <span>{group.title}</span>
                <span className="cghs-eligibility-accordion-icon" aria-hidden="true">
                  {isOpen ? "−" : "+"}
                </span>
              </button>
              {isOpen && (
                <ul className="cghs-eligibility-accordion-body">
                  {group.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
