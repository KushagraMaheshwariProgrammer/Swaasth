import {
  DISPUTE_TIMELINE_NOTICE,
  DISPUTE_TIMELINES,
} from "../data/disputeTimelines";

export default function DisputeTimelineReminders() {
  return (
    <section className="audit-section dispute-timeline-section">
      <details>
        <summary>Timeline and limitation reminders</summary>
        <p className="treatment-audit-disclaimer">{DISPUTE_TIMELINE_NOTICE}</p>
        <div className="dispute-timeline-list">
          {DISPUTE_TIMELINES.map((entry) => (
            <article key={entry.title} className="dispute-timeline-card">
              <h4>{entry.title}</h4>
              <p>
                <strong>Typical timing:</strong> {entry.timing}
              </p>
              <ul>
                {entry.actions.map((action) => (
                  <li key={action}>{action}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </details>
    </section>
  );
}
