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

export const HOSPITALISATION_RELIEF_ELIGIBILITY_SECTIONS = [
  {
    title: "Hospitalisation Relief Scheme – Eligibility",
    items: [
      "Available for registered building and other construction workers under the Telangana Building & Other Construction Workers Welfare Board.",
      "The worker must have been hospitalized for at least 5 days due to an accident or disease.",
      "Relief may be extended up to 3 months in severe or terminal conditions, subject to approval.",
    ],
  },
  {
    title: "Benefit",
    items: [
      "₹300 per day of hospitalization.",
      "Maximum reimbursement/relief: ₹4,500 per month.",
    ],
  },
];

export const KCR_KIT_ELIGIBILITY_SECTIONS = [
  {
    title: "KCR Kit / Pregnancy Nutrition Kit – Eligibility",
    items: [
      "Patient must be a pregnant woman.",
      "Patient must be at least 18 years old.",
      "Patient must be a resident of Telangana.",
      "Family monthly income should be below ₹10,000.",
      "Patient should be identified/verified through Anganwadi Worker process where applicable.",
      "Patient should preferably have Telangana-linked Aadhaar details as required by the scheme rules.",
    ],
  },
  {
    title: "Exclusions",
    items: [
      "Not eligible if the beneficiary has more than two live children.",
      "Not eligible if treatment is taken from a non-government/private hospital.",
      "Not eligible if Aadhaar does not belong to Telangana.",
      "Non-residents of Telangana are not eligible.",
    ],
  },
];

export const RAJIV_AAROGYASRI_ELIGIBILITY_SECTIONS = [
  {
    title: "Rajiv Aarogyasri / Aarogyasri Cheyutha – Eligibility",
    items: [
      "Beneficiary should be a resident of Telangana.",
      "Beneficiary should hold an Aarogyasri / eligible ration card or otherwise qualify under the scheme.",
      "Aadhaar is commonly required for beneficiary verification.",
      "Treatment should be at an empanelled hospital and for an approved Aarogyasri package where applicable.",
    ],
  },
  {
    title: "Coverage notes",
    items: [
      "Rajiv Aarogyasri is a cashless package-based scheme for eligible beneficiaries.",
      "Approved package rates are used for comparison; final approval depends on hospital empanelment and package eligibility.",
      "Cancer-related treatment may require verification with approved oncology centres.",
    ],
  },
];

export const AAROGYA_BHADRATHA_COVERAGE_LIMITS = [
  {
    title: "Per-Case Reimbursement Limits (G.O.Ms.No.101, 1-12-2015)",
    items: [
      "General ailments: Up to Rs. 5,00,000 per treatment episode.",
      "Major ailments (heart surgery, kidney transplant, cancer, neuro-surgery): Up to Rs. 7,50,000 per treatment.",
      "If treatment cost exceeds the package limit, the CEO of EHS may review on a case-by-case basis.",
    ],
  },
  {
    title: "Annual Family Limits (Financial Year)",
    intro:
      "The scheme covers a family (self + spouse + up to 3 children under 25 + parents) with the following annual limits:",
    items: [
      "Up to Rs. 8,00,000 per year: Automatic coverage without additional approval.",
      "Rs. 8,00,000 to Rs. 15,00,000: Requires DGP approval.",
      "Beyond Rs. 15,00,000: Requires Trust Board approval.",
    ],
  },
  {
    title: "Payment Basis by Hospital Type",
    items: [
      "Non-NABH and regular NABH hospitals: Payment at EHS package rates. Packages are all-inclusive (investigations, medicines, implants, consumables, diet, complications, and 10-day follow-up).",
      "NABH Super Specialty hospitals: Surgical procedures at package rates, plus consumables (implants, stents, mesh) at actual cost. Medical management (non-surgical) is on actual claims basis with bill scrutiny.",
      "Hospital rates: Used as fallback only for procedures not covered in the EHS schedule.",
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
