import LegalDocument from "../components/LegalDocument";
import {
  THIRD_PARTY_NOTICE_SECTIONS,
  THIRD_PARTY_NOTICES_LAST_UPDATED,
} from "../data/thirdPartyNotices";

export default function ThirdPartyLicensesPage() {
  return (
    <LegalDocument
      title="Third-party licenses"
      lastUpdated={THIRD_PARTY_NOTICES_LAST_UPDATED}
      sections={THIRD_PARTY_NOTICE_SECTIONS}
      lead="Open-source components used by Swaasth. The application itself is AGPL-3.0. See also NOTICE in the source repository and the Open source page."
    />
  );
}
