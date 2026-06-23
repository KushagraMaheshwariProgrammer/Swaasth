export const CGHS_ELIGIBILITY_TITLE = "CGHS Eligibility Criteria";

export const CGHS_ELIGIBILITY_SUBTITLE =
  "Central Government Health Scheme eligibility depends on beneficiary category and residence in a CGHS-covered city.";

export const CGHS_ELIGIBILITY_BADGE = "Eligibility Advisory";

export const CGHS_RESIDENCE_RULE =
  "Residence, and not headquarters, is the criterion for determining eligibility of a Central Government servant for availing medical facilities under CGHS. Central Government employees and eligible family members residing in notified CGHS-covered cities are covered under the scheme.";

export const CGHS_IMPORTANT_NOTE =
  "This section is an eligibility advisory based on CGHS beneficiary categories. Final eligibility, CGHS card validity, dependent status, city coverage, contribution requirements, and entitlement must be verified through official CGHS/MoHFW sources or the concerned CGHS Wellness Centre.";

export const CGHS_FALLBACK_NOTE =
  "CGHS rates are being used as a benchmark/fallback. CGHS eligibility is separate and must be verified.";

export const CGHS_BENEFICIARY_CATEGORIES = [
  { id: "central_gov_employee", label: "Central Government employee" },
  { id: "central_gov_pensioner", label: "Central Government pensioner" },
  {
    id: "dependent_family_member",
    label: "Dependent/family member of eligible beneficiary",
  },
  {
    id: "mp_ex_mp_judge",
    label: "MP / Ex-MP / Judge / constitutional category",
  },
  {
    id: "capf_cisf_defence_railway_audit",
    label: "CAPF/CISF/Defence/Railway/Audit related category",
  },
  {
    id: "journalist_special",
    label: "Accredited journalist / special eligible category",
  },
  { id: "not_sure", label: "Not sure" },
];

export const CGHS_ELIGIBILITY_GROUPS = [
  {
    id: "central_gov_employees",
    title: "Central Government Employees and Pensioners",
    items: [
      "All Central Government employees paid from Central Civil Estimates, except Railways and Delhi Administration, including their families.",
      "Pensioners of Central Government, except pensioners belonging to Railways and Armed Forces, including their families.",
      "Central Government pensioners retiring with Contributory Provident Fund benefits and their families.",
      "Widows of Central Government pensioners receiving family pension.",
      "Central Government servants deputed to semi-government/autonomous bodies receiving substantial Central Government grants.",
      "Central Government employees on deputation to statutory/autonomous bodies during deputation.",
      "Work-charged and industrial staff working in establishments run by Central Government ministries/departments from the date of joining.",
      "PSU absorbees who had commuted 100% pension and later restored 1/3rd pension after 15 years.",
    ],
  },
  {
    id: "defence_police_capf",
    title: "Defence, Police, CAPF, and Related Personnel",
    items: [
      "Delhi Police personnel and their families, in Delhi only.",
      "Civilian employees of Defence paid from Defence Service Estimates, except in Mumbai where applicable.",
      "Military officers on deputation to civil departments and paid from Central Civil Estimates.",
      "CISF personnel and families, and CAPF personnel posted in CGHS cities.",
      "Defence Industrial Employees of Naval Dockyard, Central Ordnance Depot and AFMSD in Mumbai.",
    ],
  },
  {
    id: "railway_audit",
    title: "Railway and Audit Related Categories",
    items: [
      "Railway Board employees.",
      "Serving and retired Railway Audit Staff.",
      "Pensioners of Ordnance factories.",
      "Employees of Ordnance Factory Board Headquarters, Kolkata and Ordnance Equipment Factories Headquarters, Kanpur.",
      "Retired Divisional Accountants of Indian Audit and Accounts Department whose pay/pension are borne by State Governments.",
      "Retired Divisional Accounts Officers and Divisional Accountants of the Office of Comptroller and Auditor General of India.",
    ],
  },
  {
    id: "constitutional",
    title: "Constitutional / Public Functionaries",
    items: [
      "Ex-Governors and Lt. Governors and their families.",
      "Ex-Vice Presidents and their families.",
      "Parliamentary Secretaries of the Central Government and their families.",
      "Members of Parliament and their families.",
      "Ex-Members of Parliament.",
      "Family members of deceased Ex-Members of Parliament.",
      "Sitting Judges of Supreme Court and High Court of Delhi.",
      "Former Judges of Supreme Court and High Courts.",
    ],
  },
  {
    id: "special_categories",
    title: "Special Eligible Categories",
    items: [
      "Freedom Fighters and family members receiving Central Pension under Swatantrata Sainik Samman Pension Scheme.",
      "Accredited Journalist producing certificate from Press Council of India stating membership of Press Association, New Delhi, for OPD and at RML Hospital.",
      "Members of Staff Side of the National Council of Joint Consultative Machinery, even if not serving as Central Government employees.",
      "Employees of Kendriya Vidyalaya Sangathan stationed at Delhi & NCR, Kolkata, Chennai, Hyderabad, Mumbai and Bengaluru.",
      "Employees of Supreme Court Legal Services Committee.",
      "Employees of India Pharmacopoeia Commission and their families.",
      "Persons employed in semi-government/autonomous bodies permitted to join CGHS.",
      "Employees of statutory/autonomous bodies of Central Government who receive Central Civil Pension.",
      "All India Service pensioners who retire while serving under the State, at their option.",
    ],
  },
  {
    id: "family_dependents",
    title: "Family / Dependent Coverage Situations",
    items: [
      "Families of Government servants transferred to a non-CGHS area, for maximum six months on advance CGHS contribution payment.",
      "Families of IAS officers on North-Eastern Cadre staying back in Delhi after officer repatriation, if they continue to occupy Government accommodation and pay CGHS contribution in advance.",
      "Same applies to families of IAS officers of J&K Cadre.",
      "Child drawing pension on death of a Central Government employee, including minor brothers and sisters of such child.",
      "Family/dependent members of a CGHS beneficiary who stay back in CGHS-covered area after posting of employee to N.E. region including Sikkim, Andaman & Nicobar, Lakshadweep, Ladakh, or CAPF personnel posted in Left Wing Extremist areas, on payment of annual CGHS contribution in advance.",
    ],
  },
];

const PREVIEW_MAY_BE_ELIGIBLE =
  "Patient may fall under a CGHS eligible category, subject to CGHS card and official verification.";
const PREVIEW_NOT_CONFIRMED =
  "CGHS eligibility could not be confirmed from the information provided. Verify beneficiary category and CGHS card status.";
const PREVIEW_CITY_REQUIRED =
  "CGHS eligibility/facility access depends on residence in a notified CGHS-covered city or applicable special rules.";

export function buildCghsEligibilityPreview({
  beneficiaryCategory = null,
  residesInCoveredCity = null,
} = {}) {
  const messages = [];
  const categoryConfirmed =
    beneficiaryCategory && beneficiaryCategory !== "not_sure";

  if (residesInCoveredCity === false) {
    messages.push(PREVIEW_CITY_REQUIRED);
  }

  if (categoryConfirmed && residesInCoveredCity === true) {
    messages.push(PREVIEW_MAY_BE_ELIGIBLE);
  } else if (!categoryConfirmed || beneficiaryCategory === "not_sure") {
    messages.push(PREVIEW_NOT_CONFIRMED);
  }

  return messages;
}

/**
 * Whether CGHS eligibility advisory should appear on a report and how to display it.
 */
export function getCghsEligibilityDisplayMode(report) {
  const settings = report?.comparison_settings || {};
  const comparisonScheme = settings.comparison_scheme || "cghs";
  const cghsFallbackFromAarogya = Boolean(settings.cghs_fallback_from_aarogya);
  const hasItemFallback = (report?.line_items || []).some(
    (item) => item.aarogyasri_fallback_used
  );

  if (comparisonScheme === "cghs") {
    return {
      show: true,
      mode: cghsFallbackFromAarogya ? "fallback" : "full",
    };
  }

  if (cghsFallbackFromAarogya || hasItemFallback) {
    return { show: true, mode: "fallback" };
  }

  return { show: false, mode: null };
}
