const MIN_BIRTH_YEAR = 1900;
const MAX_AGE = 150;

export function getCurrentYear() {
  return new Date().getFullYear();
}

export function deriveAgeFromBirthYear(birthYear) {
  const year = Number(birthYear);
  if (!Number.isFinite(year)) {
    return null;
  }
  const age = getCurrentYear() - year;
  if (age < 0 || age > MAX_AGE) {
    return null;
  }
  return age;
}

export function validateBirthYearInput(value) {
  const year = Number(value);
  const currentYear = getCurrentYear();
  if (!Number.isFinite(year) || !Number.isInteger(year)) {
    throw new Error("Please enter a valid birth year.");
  }
  if (year < MIN_BIRTH_YEAR) {
    throw new Error(`Birth year must be ${MIN_BIRTH_YEAR} or later.`);
  }
  if (year > currentYear) {
    throw new Error("Birth year cannot be in the future.");
  }
  return year;
}

export function getPatientBirthYear(patient) {
  if (patient?.birthYear != null) {
    const year = Number(patient.birthYear);
    if (Number.isFinite(year)) {
      return year;
    }
  }
  if (patient?.age != null) {
    const age = Number(patient.age);
    if (Number.isFinite(age) && age >= 0 && age <= MAX_AGE) {
      return getCurrentYear() - Math.round(age);
    }
  }
  return null;
}

export function getPatientAge(patient) {
  const fromBirthYear = deriveAgeFromBirthYear(getPatientBirthYear(patient));
  if (fromBirthYear != null) {
    return fromBirthYear;
  }
  const age = Number(patient?.age);
  if (Number.isFinite(age) && age >= 0 && age <= MAX_AGE) {
    return Math.round(age);
  }
  return null;
}

export function formatPatientAge(patient) {
  const age = getPatientAge(patient);
  return age != null ? `${age} yrs` : "—";
}

export function patientAgeApiPayload(patient) {
  if (!patient) {
    return { patient_birth_year: null, patient_age: null };
  }
  const birthYear = getPatientBirthYear(patient);
  return {
    patient_birth_year: birthYear,
    patient_age: getPatientAge(patient),
  };
}
