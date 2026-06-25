import YesNoNotSureSelector from "./YesNoNotSureSelector";

export default function SchemeYesNoQuestion({
  id,
  question,
  name,
  value,
  onChange,
  optional = false,
  showNotSure = false,
}) {
  return (
    <div className="scheme-card-followup scheme-card-followup-compact">
      <YesNoNotSureSelector
        id={id}
        label={
          <>
            {question}
            {optional ? (
              <span className="scheme-question-optional"> (optional)</span>
            ) : null}
          </>
        }
        name={name}
        value={value}
        onChange={onChange}
        showNotSure={showNotSure}
      />
    </div>
  );
}
