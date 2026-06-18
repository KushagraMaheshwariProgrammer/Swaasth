export default function SchemeYesNoQuestion({
  id,
  question,
  name,
  value,
  onChange,
  optional = false,
}) {
  return (
    <div
      className="scheme-card-followup scheme-card-followup-compact"
      role="group"
      aria-labelledby={id}
    >
      <p id={id} className="scheme-card-followup-question">
        {question}
        {optional ? (
          <span className="scheme-question-optional"> (optional)</span>
        ) : null}
      </p>
      <div className="scheme-card-choice-group">
        <label className="scheme-card-choice">
          <input
            type="radio"
            name={name}
            checked={value === true}
            onChange={() => onChange(true)}
          />
          <span>Yes</span>
        </label>
        <label className="scheme-card-choice">
          <input
            type="radio"
            name={name}
            checked={value === false}
            onChange={() => onChange(false)}
          />
          <span>No</span>
        </label>
      </div>
    </div>
  );
}
