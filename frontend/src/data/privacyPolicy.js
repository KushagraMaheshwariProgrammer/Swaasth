export const PRIVACY_POLICY_VERSION = "2026-08-03";
export const PRIVACY_POLICY_LAST_UPDATED = "3 August 2026";
export const PRIVACY_POLICY_SECTIONS = [
  {
    title: "Introduction",
    paragraphs: [
      "This Privacy Policy explains how Swaasth (\"Swaasth\", \"we\", \"us\", or \"our\") collects, uses, stores, shares, protects, retains, and deletes your information when you use the Swaasth mobile application, website, and related services.",
      "Swaasth helps users review hospital bills, prescriptions, and other healthcare documents for possible billing irregularities, and provides guidance on possible next steps. Because of the nature of this service, we may process sensitive personal information, including health-related information. We take this responsibility seriously.",
      "This Privacy Policy should be read together with our Terms and Conditions. By creating an account, signing in, uploading documents, or using any feature of Swaasth, you consent to the practices described in this Privacy Policy. If you do not agree, please do not use Swaasth.",
    ],
    bullets: [],
  },
  {
    title: "1. Scope and Applicable Law",
    paragraphs: [
      "This Privacy Policy applies to all users of the Swaasth application and website, and to all personal data processed through them.",
      "We process personal data in accordance with applicable Indian law, including the Digital Personal Data Protection Act, 2023 (DPDP Act), the Information Technology Act, 2000, and the rules made under them, to the extent applicable.",
    ],
    bullets: [],
  },
  {
    title: "2. Information We Collect",
    paragraphs: [
      "We collect the following categories of information:",
    ],
    bullets: [
      "Account information: your email address, sign-in method (email/password or Google sign-in), and account identifiers provided by our authentication service.",
      "Patient details you provide: patient name, year of birth, gender, city and state, and clinical or medical history details you choose to enter for the patients you manage.",
      "Documents you upload: hospital bills, prescriptions, discharge summaries, diagnostic reports, estimates, insurance documents, and other healthcare documents, in PDF or image form, submitted for analysis.",
      "Analysis outputs: structured summaries, extracted line items, flags, reports, recommendations, and complaint or advocacy drafts generated from your documents, where you have consented to saving them.",
      "Hospital and provider details: names and details of hospitals, clinics, diagnostic centers, pharmacies, or insurers referenced in your documents or entered by you.",
      "Support communications: messages, complaints, grievances, or requests you send to us, and our responses.",
      "Technical information: basic device and usage information necessary to operate, secure, and debug the service, such as authentication tokens, timestamps, and error logs.",
    ],
  },
  {
    title: "3. Information We Do Not Collect or Store",
    paragraphs: [
      "We have designed Swaasth to minimise the data we keep. In particular:",
    ],
    bullets: [
      "We do not permanently store the original files (PDFs or images) you upload on our servers. Uploaded documents are processed to extract the information needed for analysis and are not retained as files after processing.",
      "We do not store raw OCR text extracted from your documents in our cloud database. Our database rules explicitly block such content from being saved.",
      "We do not collect your device's GPS location. City and state information is only what you choose to enter or select.",
      "We do not access your camera or microphone. Documents are provided through your device's file picker.",
      "We do not use your data for advertising, and we do not sell your personal data to anyone.",
    ],
  },
  {
    title: "4. How We Use Your Information",
    paragraphs: [
      "We use the information described above for the following purposes:",
    ],
    bullets: [
      "Creating, maintaining, and securing your account.",
      "Analysing your uploaded bills and healthcare documents to identify possible billing irregularities, overcharges, duplicates, or clinical mismatches.",
      "Generating summaries, reports, alerts, recommendations, complaint drafts, and suggested next steps.",
      "Saving analysis reports and medical history to your account, only where you have given specific consent.",
      "Providing legal guidance, advisory assistance, and procedural support features.",
      "Responding to your support requests, complaints, grievances, or data-related requests.",
      "Maintaining the security, integrity, and reliability of the service, including preventing fraud, abuse, and unauthorized access.",
      "Improving the app's features, accuracy, and user experience.",
      "Complying with applicable law, legal process, or lawful requests from competent authorities.",
    ],
  },
  {
    title: "5. Legal Basis and Consent",
    paragraphs: [
      "We process your personal data on the basis of the consent you provide when you accept our Terms and Conditions and this Privacy Policy, and when you give specific consents inside the app (such as the medical history consent).",
      "Where you upload documents or enter details relating to another person (for example, a family member who is the patient), you confirm that you are the patient's legal guardian, authorized family member, or authorized representative, or are otherwise legally permitted to share that information with us.",
      "We may also process limited personal data without separate consent where permitted by law, for example to comply with a legal obligation, respond to a court order, or protect the security of the service.",
    ],
    bullets: [],
  },
  {
    title: "6. Specific Consent for Medical History",
    paragraphs: [
      "Saving analysis reports and medical history to your account is optional and controlled by a separate, specific consent inside the app.",
      "If you decline or do not give this consent, you can still analyse documents, but structured reports and medical history will not be saved to your cloud account.",
      "You can withdraw this consent at any time from Account settings. If you revoke it, previously saved reports and medical documents are deleted from your account and from your device's local storage.",
    ],
    bullets: [],
  },
  {
    title: "7. Automated Processing and Artificial Intelligence",
    paragraphs: [
      "Swaasth uses automated tools, including optical character recognition (OCR) and artificial intelligence models (currently provided through Microsoft Azure OpenAI services), to read and analyse the documents you submit.",
      "Content from your documents is transmitted to these processing services to generate the analysis, and is handled under contractual and technical safeguards. We do not permit our AI service providers to use your data to train their publicly available models.",
      "AI-generated output can be incomplete or incorrect. Analysis results are assistive only and are not final legal, medical, or financial findings. Please review our Terms and Conditions for the limitations that apply to analysis results.",
    ],
    bullets: [],
  },
  {
    title: "8. Where Your Data Is Stored",
    paragraphs: [
      "Your data is stored in the following places:",
      "Some of our service providers (such as Google and Microsoft) may store or process data on servers located outside India. Where personal data is transferred outside India, we take reasonable steps to ensure it receives an adequate level of protection consistent with applicable law.",
    ],
    bullets: [
      "Cloud database: account details, consent records, patient details, and analysis reports (where consented) are stored in Google Firebase (Firestore), protected by authentication and access rules that restrict each user's data to that user alone.",
      "On your device: bills, patient details, and consent records may be cached in encrypted local storage on your own device so the app works quickly and offline. This data stays on your device and is protected by encryption.",
      "Transient processing: document content is processed in memory by our backend and AI/OCR providers to generate results and is not retained as stored files after processing.",
    ],
  },
  {
    title: "9. Sharing and Disclosure",
    paragraphs: [
      "We do not sell, rent, or trade your personal data. We share personal data only in the following limited circumstances:",
    ],
    bullets: [
      "Service providers: with vendors who help us operate the service, such as Google Firebase (authentication and database) and Microsoft Azure (AI analysis), strictly for the purposes described in this Policy and under appropriate safeguards.",
      "At your direction: when you choose to export, download, share, or send a report, complaint, or document to a hospital, insurer, authority, or any other person, that sharing is initiated and controlled by you.",
      "Legal requirements: where disclosure is required by applicable law, court order, or a lawful request from a competent government authority.",
      "Protection of rights: where reasonably necessary to protect the rights, property, safety, or security of Swaasth, our users, or the public, including investigating fraud or abuse.",
      "Business transfers: if Swaasth is involved in a merger, acquisition, or transfer of assets, your data may be transferred as part of that transaction, subject to this Privacy Policy or an equivalent standard of protection.",
    ],
  },
  {
    title: "10. Data Retention",
    paragraphs: [
      "We retain personal data only for as long as it is needed for the purposes described in this Policy:",
    ],
    bullets: [
      "Account and consent records are retained while your account is active.",
      "Patient details and saved analysis reports are retained until you delete them, revoke medical history consent, or delete your account.",
      "Original uploaded files and raw OCR text are not retained after processing, as described in Section 3.",
      "Support communications are retained for as long as reasonably needed to resolve the matter and maintain records of grievances.",
      "We may retain limited data for longer where required by law, to resolve disputes, to enforce our agreements, or for security purposes.",
    ],
  },
  {
    title: "11. Your Rights",
    paragraphs: [
      "Subject to applicable law, including the DPDP Act, you have the following rights over your personal data:",
      "To exercise any of these rights, use the controls available in the app (Account settings) or contact us using the details in Section 16. We may need to verify your identity before acting on a request.",
    ],
    bullets: [
      "Access: request a summary of the personal data we hold about you and how it is processed.",
      "Correction: request correction of inaccurate or incomplete personal data, or update it directly in the app.",
      "Erasure: request deletion of your personal data, including patient details and saved reports.",
      "Withdrawal of consent: withdraw any consent you have given at any time, with effect for the future. Withdrawing consent may limit the features available to you.",
      "Grievance redressal: raise a complaint about how your data is handled and receive a timely response.",
      "Nomination: nominate another individual to exercise your rights in the event of your death or incapacity, as provided under the DPDP Act.",
    ],
  },
  {
    title: "12. Deleting Your Data and Account",
    paragraphs: [
      "You can delete individual patients, bills, and reports from within the app.",
      "You can revoke medical history consent from Account settings, which deletes previously saved reports and medical documents from your account and your device.",
      "To request deletion of your entire account and associated data, contact us at the email address in Section 16. We will act on verified requests within a reasonable time, except where we are required or permitted by law to retain certain records.",
    ],
    bullets: [],
  },
  {
    title: "13. Security",
    paragraphs: [
      "We use reasonable technical and organisational safeguards to protect your data, including:",
      "No system is completely secure. You are responsible for keeping your login credentials confidential and for notifying us immediately of any suspected unauthorized access to your account.",
    ],
    bullets: [
      "Authentication for every request, so only you can access your account's data.",
      "Database security rules that restrict each user's records to that user alone and block prohibited content (such as raw OCR text) from being stored.",
      "Encryption of data in transit (HTTPS/TLS) and encryption of locally cached data on your device.",
      "Minimising stored data by not retaining original uploaded files after processing.",
      "Access controls and monitoring on our backend systems.",
    ],
  },
  {
    title: "14. Children's Privacy",
    paragraphs: [
      "Swaasth is intended for use by adults (18 years of age or older). We do not knowingly allow children to create accounts or knowingly collect personal data directly from children.",
      "Documents you upload may relate to a patient who is a minor (for example, your child). In that case, you confirm that you are the minor's parent or lawful guardian and that you consent to the processing of the minor's information as described in this Policy.",
      "If you believe a child has created an account or that we have collected a child's data without appropriate consent, please contact us and we will take appropriate steps to delete it.",
    ],
    bullets: [],
  },
  {
    title: "15. Changes to This Privacy Policy",
    paragraphs: [
      "We may update this Privacy Policy from time to time to reflect changes in our practices, technology, or legal requirements.",
      "When we make material changes, we will notify you inside the app or on our website, and where required by law we will seek your consent again.",
      "The \"Last updated\" date at the top of this Policy indicates when it was most recently revised. Your continued use of Swaasth after changes take effect means you accept the updated Policy.",
    ],
    bullets: [],
  },
  {
    title: "16. Contact and Grievance Officer",
    paragraphs: [
      "For questions about this Privacy Policy, to exercise your rights, or to raise a grievance about how your personal data is handled, you may contact:",
      "We will acknowledge and respond to grievances within a reasonable time, and in any event within the timelines required under applicable law.",
    ],
    bullets: [
      "Swaasth Support / Grievance Contact — Email: swaasth.app@gmail.com",
    ],
  },
];
