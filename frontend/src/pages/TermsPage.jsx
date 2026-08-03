import LegalDocument from "../components/LegalDocument";
import {
  TERMS_LAST_UPDATED,
  TERMS_SECTIONS,
} from "../data/termsAndConditions";

export default function TermsPage() {
  return (
    <LegalDocument
      title="Terms and Conditions"
      lastUpdated={TERMS_LAST_UPDATED}
      sections={TERMS_SECTIONS}
      lead="These Terms govern your use of Swaasth. They should be read together with the Privacy Policy."
    />
  );
}
