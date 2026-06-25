const DEFAULT_OPTIONS = [
  { value: true, label: "Yes" },
  { value: false, label: "No" },
  { value: null, label: "Not sure" },
];

export default function YesNoNotSureSelector({
  id,
  label,
  name,
  value,
  onChange,
  helperText,
  disabled = false,
  showNotSure = true,
}) {
  const options = showNotSure
    ? DEFAULT_OPTIONS
    : DEFAULT_OPTIONS.filter((option) => option.value !== null);

  return (
    <fieldset
      className="yes-no-not-sure-fieldset"
      disabled={disabled}
      aria-labelledby={id}
    >
      <legend id={id} className="yes-no-not-sure-label">
        {label}
      </legend>
      {helperText ? (
        <p className="yes-no-not-sure-helper">{helperText}</p>
      ) : null}
      <div
        className="yes-no-not-sure-group"
        role="radiogroup"
        aria-labelledby={id}
      >
        {options.map((option) => {
          const selected = value === option.value;
          return (
            <label
              key={`${name}-${String(option.value)}`}
              className={`yes-no-not-sure-option${selected ? " is-selected" : ""}`}
            >
              <input
                type="radio"
                name={name}
                value={String(option.value)}
                checked={selected}
                disabled={disabled}
                onChange={() => onChange(option.value)}
              />
              <span>{option.label}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
