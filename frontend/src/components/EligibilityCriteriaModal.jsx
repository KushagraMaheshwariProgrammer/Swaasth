export const PMJAY_ELIGIBILITY_SECTIONS = [
  {
    title: "Main PM-JAY eligibility categories",
    intro:
      "Rural households qualify if they fall into at least one of these deprivation categories:",
    items: [
      "One-room house with kutcha walls and roof",
      "No adult member aged 16–59",
      "Female-headed household with no adult male aged 16–59",
      "Disabled member and no able-bodied adult member",
      "SC/ST household",
      "Landless household dependent on manual casual labour",
    ],
  },
  {
    title: "Automatically included rural categories",
    items: [
      "Homeless households",
      "Destitute families/living on alms",
      "Manual scavenger families",
      "Particularly Vulnerable Tribal Groups (PVTGs)",
      "Released bonded labourers",
    ],
  },
  {
    title: "Urban occupational categories",
    intro:
      "Urban households are covered based on occupational categories, including:",
    items: [
      "Domestic workers",
      "Street vendors",
      "Construction workers",
      "Sanitation workers",
      "Transport workers (drivers, conductors, rickshaw pullers, etc.)",
      "Tailors, artisans, mechanics, electricians, helpers, delivery assistants, and several other low-income occupations",
    ],
  },
  {
    title: "Senior citizens",
    items: [
      "All senior citizens aged 70 years and above are now eligible for Ayushman Bharat PM-JAY regardless of income or socio-economic category.",
    ],
  },
];

export const AAROGYA_BHADRATHA_ELIGIBILITY_SECTIONS = [
  {
    title: "Aarogya Bhadratha Scheme – Eligibility Criteria",
    items: [
      "All categories of employees working in the Police Department on a regular basis.",
      "Male and female children of members are eligible up to 25 years of age, restricted to a maximum of three children. Gainfully employed sons and married daughters are excluded.",
      "Stipendiary recruits, including Induction Trainee Police Constables and Sub-Inspectors.",
      "Boarders residing in Police Boys Hostels.",
      "Widows of police personnel who died in extremist or terrorist activities.",
      "Membership under the scheme continues only until retirement.",
    ],
  },
];

export default function EligibilityCriteriaModal({
  open,
  onClose,
  title = "Ayushman Bharat PM-JAY eligibility",
  sections = PMJAY_ELIGIBILITY_SECTIONS,
}) {
  if (!open) {
    return null;
  }

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="eligibility-modal-title"
      onClick={onClose}
    >
      <div
        className="modal-panel eligibility-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="modal-header">
          <h2 id="eligibility-modal-title">{title}</h2>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </header>
        <div className="modal-body eligibility-modal-body">
          {sections.map((section) => (
            <section key={section.title} className="eligibility-section">
              <h3>{section.title}</h3>
              {section.intro && <p>{section.intro}</p>}
              <ul>
                {section.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
          ))}
        </div>
        <footer className="modal-footer">
          <button type="button" className="analyze-btn" onClick={onClose}>
            Got it
          </button>
        </footer>
      </div>
    </div>
  );
}
