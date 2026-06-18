import { useEffect, useState } from "react";
import EligibilityCriteriaModal, {
  AAROGYA_BHADRATHA_ELIGIBILITY_SECTIONS,
  AAROGYA_BHADRATHA_COVERAGE_LIMITS,
  HOSPITALISATION_RELIEF_ELIGIBILITY_SECTIONS,
  KCR_KIT_ELIGIBILITY_SECTIONS,
  PMJAY_ELIGIBILITY_SECTIONS,
} from "./EligibilityCriteriaModal";
import KcrKitQuestionsModal, {
  emptyKcrKitAnswers,
} from "./KcrKitQuestionsModal";
import SchemeYesNoQuestion from "./SchemeYesNoQuestion";
import { getStateOptions, isTelanganaState } from "../services/locations";

export const GENDER_OPTIONS = [
  { id: "male", label: "Male" },
  { id: "female", label: "Female" },
  { id: "other", label: "Other" },
  { id: "prefer_not_to_say", label: "Prefer not to say" },
];

export const emptyKcrKitFields = () => ({
  kcrKitSelected: false,
  kcrIsPregnant: false,
  kcrIsTelanganaResident: false,
  kcrAge18OrAbove: false,
  kcrIncomeBelow10000: false,
  kcrGovernmentHospitalTreatment: false,
  kcrMoreThanTwoLiveChildren: false,
  kcrAadhaarTelangana: false,
  kcrIdentifiedByAnganwadiWorker: false,
});

export const emptyPatientForm = () => ({
  name: "",
  age: "",
  gender: "",
  state: "",
  ayushmanEligible: false,
  aarogyaBhadrathaEligible: false,
  hospitalisationReliefSchemeSelected: false,
  isRegisteredConstructionWorker: false,
  ...emptyKcrKitFields(),
  savePastBills: false,
});

export function patientToFormFields(patient) {
  return {
    name: patient?.name || "",
    age: patient?.age != null ? String(patient.age) : "",
    gender: patient?.gender || "",
    state: patient?.state || "",
    ayushmanEligible: Boolean(patient?.ayushmanEligible),
    aarogyaBhadrathaEligible: Boolean(patient?.aarogyaBhadrathaEligible),
    hospitalisationReliefSchemeSelected: Boolean(
      patient?.hospitalisationReliefSchemeSelected
    ),
    isRegisteredConstructionWorker: Boolean(
      patient?.isRegisteredConstructionWorker
    ),
    kcrKitSelected: Boolean(patient?.kcrKitSelected),
    kcrIsPregnant: Boolean(patient?.kcrIsPregnant),
    kcrIsTelanganaResident: Boolean(patient?.kcrIsTelanganaResident),
    kcrAge18OrAbove: Boolean(patient?.kcrAge18OrAbove),
    kcrIncomeBelow10000: Boolean(patient?.kcrIncomeBelow10000),
    kcrGovernmentHospitalTreatment: Boolean(
      patient?.kcrGovernmentHospitalTreatment
    ),
    kcrMoreThanTwoLiveChildren: Boolean(patient?.kcrMoreThanTwoLiveChildren),
    kcrAadhaarTelangana: Boolean(patient?.kcrAadhaarTelangana),
    kcrIdentifiedByAnganwadiWorker: Boolean(
      patient?.kcrIdentifiedByAnganwadiWorker
    ),
    savePastBills: Boolean(patient?.savePastBills),
  };
}

export function genderLabel(gender) {
  return (
    GENDER_OPTIONS.find((option) => option.id === gender)?.label || gender || "—"
  );
}

const STATE_OPTIONS = getStateOptions();

function getKcrAnswersFromForm(form) {
  return {
    kcrIsPregnant: Boolean(form.kcrIsPregnant),
    kcrIsTelanganaResident: Boolean(form.kcrIsTelanganaResident),
    kcrIncomeBelow10000: Boolean(form.kcrIncomeBelow10000),
    kcrGovernmentHospitalTreatment: Boolean(form.kcrGovernmentHospitalTreatment),
    kcrMoreThanTwoLiveChildren: Boolean(form.kcrMoreThanTwoLiveChildren),
    kcrAadhaarTelangana: Boolean(form.kcrAadhaarTelangana),
    kcrIdentifiedByAnganwadiWorker: Boolean(form.kcrIdentifiedByAnganwadiWorker),
  };
}

export default function PatientForm({
  form,
  setForm,
  onSubmit,
  onCancel,
  submitLabel,
  saving,
  error,
  info,
}) {
  const [activeModal, setActiveModal] = useState(null);

  const showAarogyaCard = isTelanganaState(form.state);
  const patientAge = Number(form.age);
  const showKcrKitCard =
    showAarogyaCard && Number.isFinite(patientAge) && patientAge >= 18;

  // When the patient is no longer in Telangana, the Aarogya Bhadratha scheme
  // does not apply, so reset its eligibility flag.
  useEffect(() => {
    if (!showAarogyaCard && form.aarogyaBhadrathaEligible) {
      setForm((prev) => ({ ...prev, aarogyaBhadrathaEligible: false }));
    }
  }, [showAarogyaCard, form.aarogyaBhadrathaEligible, setForm]);

  useEffect(() => {
    if (!showAarogyaCard && form.hospitalisationReliefSchemeSelected) {
      setForm((prev) => ({
        ...prev,
        hospitalisationReliefSchemeSelected: false,
        isRegisteredConstructionWorker: false,
      }));
    }
  }, [showAarogyaCard, form.hospitalisationReliefSchemeSelected, setForm]);

  useEffect(() => {
    if (!showKcrKitCard && form.kcrKitSelected) {
      setForm((prev) => ({ ...prev, ...emptyKcrKitFields() }));
    }
  }, [showKcrKitCard, form.kcrKitSelected, setForm]);

  return (
    <form className="patient-form" onSubmit={onSubmit}>
      <label className="setting-field setting-field-full">
        <span>Patient name</span>
        <input
          type="text"
          value={form.name}
          required
          placeholder="Full name"
          onChange={(event) =>
            setForm((prev) => ({ ...prev, name: event.target.value }))
          }
        />
      </label>
      <div className="comparison-settings-grid">
        <label className="setting-field">
          <span>Age</span>
          <input
            type="number"
            min="0"
            max="150"
            required
            value={form.age}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, age: event.target.value }))
            }
          />
        </label>
        <label className="setting-field">
          <span>Gender</span>
          <select
            required
            value={form.gender}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, gender: event.target.value }))
            }
          >
            <option value="">Select gender</option>
            {GENDER_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="setting-field setting-field-full">
        <span>State</span>
        <select
          value={form.state}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, state: event.target.value }))
          }
        >
          <option value="">Select state</option>
          {STATE_OPTIONS.map((stateName) => (
            <option key={stateName} value={stateName}>
              {stateName}
            </option>
          ))}
        </select>
      </label>

      <fieldset className="scheme-eligibility">
        <legend className="scheme-eligibility-title">Scheme eligibility</legend>
        <div className="scheme-card-list">
          <div className="scheme-card">
            <label className="scheme-card-checkbox">
              <input
                type="checkbox"
                checked={form.ayushmanEligible}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    ayushmanEligible: event.target.checked,
                  }))
                }
              />
              <span>Patient is eligible for Ayushman Bharat Scheme</span>
            </label>
            <button
              type="button"
              className="eligibility-learn-btn"
              onClick={() => setActiveModal("ayushman")}
            >
              Learn eligibility criteria
            </button>
          </div>

          {showAarogyaCard && (
            <div className="scheme-card">
              <label className="scheme-card-checkbox">
                <input
                  type="checkbox"
                  checked={form.hospitalisationReliefSchemeSelected}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      hospitalisationReliefSchemeSelected: event.target.checked,
                      isRegisteredConstructionWorker: event.target.checked
                        ? prev.isRegisteredConstructionWorker
                        : false,
                    }))
                  }
                />
                <span>Hospitalisation Relief Scheme</span>
              </label>
              {form.hospitalisationReliefSchemeSelected && (
                <SchemeYesNoQuestion
                  id="hrs-worker-question"
                  name="isRegisteredConstructionWorker"
                  question="Are you a registered building or construction worker under the Telangana Building & Other Construction Workers Welfare Board?"
                  value={form.isRegisteredConstructionWorker}
                  onChange={(nextValue) =>
                    setForm((prev) => ({
                      ...prev,
                      isRegisteredConstructionWorker: nextValue,
                    }))
                  }
                />
              )}
              <button
                type="button"
                className="eligibility-learn-btn"
                onClick={() => setActiveModal("hospitalisation-relief")}
              >
                Learn eligibility criteria
              </button>
            </div>
          )}

          {showKcrKitCard && (
            <div className="scheme-card">
              <label className="scheme-card-checkbox">
                <input
                  type="checkbox"
                  checked={form.kcrKitSelected}
                  onChange={(event) => {
                    if (!event.target.checked) {
                      setForm((prev) => ({ ...prev, ...emptyKcrKitFields() }));
                    }
                  }}
                  onClick={(event) => {
                    if (!form.kcrKitSelected) {
                      event.preventDefault();
                      setActiveModal("kcr-kit-questions");
                    }
                  }}
                />
                <span>KCR Kit / Pregnancy Nutrition Kit</span>
              </label>
              <p className="scheme-card-description">
                Nutrition kit support for eligible pregnant women in Telangana.
              </p>
              {form.kcrKitSelected && (
                <p className="scheme-card-status">Eligibility answers saved.</p>
              )}
              <div className="scheme-card-buttons">
                <button
                  type="button"
                  className="eligibility-learn-btn"
                  onClick={() => setActiveModal("kcr-kit-questions")}
                >
                  {form.kcrKitSelected
                    ? "Update eligibility answers"
                    : "Answer eligibility questions"}
                </button>
                <button
                  type="button"
                  className="eligibility-learn-btn"
                  onClick={() => setActiveModal("kcr-kit")}
                >
                  Learn eligibility criteria
                </button>
              </div>
            </div>
          )}

          {showAarogyaCard && (
            <div className="scheme-card">
              <label className="scheme-card-checkbox">
                <input
                  type="checkbox"
                  checked={form.aarogyaBhadrathaEligible}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      aarogyaBhadrathaEligible: event.target.checked,
                    }))
                  }
                />
                <span>Patient is eligible for Aarogya Bhadratha Scheme</span>
              </label>
              <div className="scheme-card-buttons">
                <button
                  type="button"
                  className="eligibility-learn-btn"
                  onClick={() => setActiveModal("aarogya")}
                >
                  Eligibility criteria
                </button>
                <button
                  type="button"
                  className="eligibility-learn-btn"
                  onClick={() => setActiveModal("aarogya-coverage")}
                >
                  Coverage limits
                </button>
              </div>
            </div>
          )}
        </div>
      </fieldset>

      <label className="patient-checkbox">
        <input
          type="checkbox"
          checked={form.savePastBills}
          onChange={(event) =>
            setForm((prev) => ({
              ...prev,
              savePastBills: event.target.checked,
            }))
          }
        />
        <span>Do you want to save this patient&apos;s past bills?</span>
      </label>

      <KcrKitQuestionsModal
        open={activeModal === "kcr-kit-questions"}
        onClose={() => setActiveModal(null)}
        onSave={(answers) => {
          setForm((prev) => ({
            ...prev,
            kcrKitSelected: true,
            ...answers,
          }));
          setActiveModal(null);
        }}
        initialValues={
          form.kcrKitSelected
            ? getKcrAnswersFromForm(form)
            : emptyKcrKitAnswers()
        }
      />

      <EligibilityCriteriaModal
        open={activeModal === "ayushman"}
        onClose={() => setActiveModal(null)}
        title="Ayushman Bharat PM-JAY eligibility"
        sections={PMJAY_ELIGIBILITY_SECTIONS}
      />
      <EligibilityCriteriaModal
        open={activeModal === "aarogya"}
        onClose={() => setActiveModal(null)}
        title="Aarogya Bhadratha Scheme eligibility"
        sections={AAROGYA_BHADRATHA_ELIGIBILITY_SECTIONS}
      />
      <EligibilityCriteriaModal
        open={activeModal === "aarogya-coverage"}
        onClose={() => setActiveModal(null)}
        title="Aarogya Bhadratha Coverage Limits"
        sections={AAROGYA_BHADRATHA_COVERAGE_LIMITS}
      />

      <EligibilityCriteriaModal
        open={activeModal === "hospitalisation-relief"}
        onClose={() => setActiveModal(null)}
        title="Hospitalisation Relief Scheme eligibility"
        sections={HOSPITALISATION_RELIEF_ELIGIBILITY_SECTIONS}
      />

      <EligibilityCriteriaModal
        open={activeModal === "kcr-kit"}
        onClose={() => setActiveModal(null)}
        title="KCR Kit / Pregnancy Nutrition Kit eligibility"
        sections={KCR_KIT_ELIGIBILITY_SECTIONS}
      />

      {info && <p className="auth-info">{info}</p>}
      {error && <p className="error-text">{error}</p>}
      <div className="patient-form-actions">
        {onCancel && (
          <button
            type="button"
            className="bill-editor-secondary"
            onClick={onCancel}
            disabled={saving}
          >
            Cancel
          </button>
        )}
        <button type="submit" className="analyze-btn" disabled={saving}>
          {saving ? "Saving..." : submitLabel}
        </button>
      </div>
    </form>
  );
}
