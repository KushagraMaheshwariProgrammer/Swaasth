import LegalDocument from "../components/LegalDocument";
import {
  PRIVACY_POLICY_LAST_UPDATED,
  PRIVACY_POLICY_SECTIONS,
} from "../data/privacyPolicy";

export default function PrivacyPolicyPage() {
  return (
    <LegalDocument
      title="Privacy Policy"
      lastUpdated={PRIVACY_POLICY_LAST_UPDATED}
      sections={PRIVACY_POLICY_SECTIONS}
      lead="This Policy explains how Swaasth handles your personal and health-related data. It should be read together with the Terms and Conditions."
    />
  );
}
