import { useState } from "react";
import { confirmPhiExport } from "../utils/confirmPhiExport";
import { POSSIBLE_ISSUE_NOTICE } from "../data/hedgingCopy";

function TemplateCard({ template }) {
  const [body, setBody] = useState(template.body || "");
  const [confirmed, setConfirmed] = useState(false);

  const handleCopy = async () => {
    if (!confirmed) {
      return;
    }
    if (
      !confirmPhiExport(
        "This will copy medical information to the clipboard (outside the app). Continue?"
      )
    ) {
      return;
    }
    const text = `Subject: ${template.subject}\n\n${body}`;
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // ignore clipboard errors on unsupported platforms
    }
  };

  const handleDownload = () => {
    if (!confirmed) {
      return;
    }
    const blob = new Blob([`Subject: ${template.subject}\n\n${body}`], {
      type: "text/plain",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${template.id || "complaint-draft"}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <article className="complaint-template-card">
      <h4>{template.audience}</h4>
      <p>
        <strong>Subject:</strong> {template.subject}
      </p>
      <textarea
        className="complaint-template-body"
        value={body}
        onChange={(event) => setBody(event.target.value)}
        rows={12}
        aria-label={`Complaint draft for ${template.audience}`}
      />
      <label className="complaint-confirm-label">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(event) => setConfirmed(event.target.checked)}
        />
        I have verified these facts
      </label>
      <p className="treatment-audit-disclaimer">
        {template.disclaimer ||
          `Note: ${POSSIBLE_ISSUE_NOTICE} Templates use neutral, factual language only. Swaasth does not make legal findings. Review with an advocate before filing formal complaints.`}
      </p>
      <div className="complaint-template-actions">
        <button
          type="button"
          className="bill-editor-secondary"
          onClick={handleCopy}
          disabled={!confirmed}
        >
          Copy to clipboard
        </button>
        <button
          type="button"
          className="bill-editor-secondary"
          onClick={handleDownload}
          disabled={!confirmed}
        >
          Download text
        </button>
      </div>
    </article>
  );
}

export default function ComplaintTemplates({ complaintTemplates }) {
  const templates = complaintTemplates || [];
  if (!templates.length) {
    return null;
  }

  return (
    <section className="audit-section complaint-templates-section">
      <h3>Complaint draft templates</h3>
      <p className="treatment-audit-disclaimer">
        {POSSIBLE_ISSUE_NOTICE} Fill-in drafts for hospital grievance or authority
        escalation. Confirm facts before copying or downloading.
      </p>
      {templates.map((template) => (
        <TemplateCard key={template.id} template={template} />
      ))}
    </section>
  );
}
