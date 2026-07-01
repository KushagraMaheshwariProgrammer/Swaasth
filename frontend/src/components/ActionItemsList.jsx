import { getActionTierMeta } from "../actionPlanUtils";

const TIER_ORDER = ["A", "B", "C"];

export default function ActionItemsList({ actionItems }) {
  const items = actionItems || [];
  if (!items.length) {
    return null;
  }

  return (
    <section className="audit-section action-items-section">
      <h3>Recommended actions</h3>
      {TIER_ORDER.map((tier) => {
        const grouped = items.filter((item) => item.tier === tier);
        if (!grouped.length) {
          return null;
        }
        const meta = getActionTierMeta(tier);
        return (
          <div key={`tier-${tier}`} className="action-tier-group">
            <div className="action-tier-header">
              <span className={meta.badgeClass}>{meta.label}</span>
              <span className="action-tier-hint">{meta.hint}</span>
            </div>
            <ul className="action-items-list">
              {grouped.map((item, index) => (
                <li key={`${item.type}-${item.item}-${index}`} className="action-item-card">
                  <p className="action-item-label">
                    {item.display_label || item.item || item.type}
                  </p>
                  <p className="action-item-text">{item.action}</p>
                  {item.attachments?.length > 0 && (
                    <p className="action-item-attachments">
                      Attach: {item.attachments.join(", ")}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </section>
  );
}
