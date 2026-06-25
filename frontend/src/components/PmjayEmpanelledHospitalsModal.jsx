import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  fetchPmjayFilters,
  searchPmjayHospitals,
} from "../services/pmjaySchemes";
import PmjayHospitalCard from "./PmjayHospitalCard";
import { formatDisplayName } from "../lib/hospitalDisplay";

function SearchIcon() {
  return (
    <svg
      className="location-picker-search-icon"
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
      <path
        d="M20 20l-4.5-4.5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function PmjayEmpanelledHospitalsModal({
  open,
  onClose,
  initialState = "",
}) {
  const [query, setQuery] = useState("");
  const [state, setState] = useState(initialState || "");
  const [district, setDistrict] = useState("");
  const [city, setCity] = useState("");
  const [hospitalType, setHospitalType] = useState("");
  const [filters, setFilters] = useState({
    states: [],
    districts: [],
    cities: [],
    hospital_types: [],
  });
  const [hospitals, setHospitals] = useState([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const searchRef = useRef(null);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    setQuery("");
    setState(initialState || "");
    setDistrict("");
    setCity("");
    setHospitalType("");
  }, [open, initialState]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    let cancelled = false;
    fetchPmjayFilters({ state, district })
      .then((payload) => {
        if (!cancelled) {
          setFilters(payload);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFilters({
            states: [],
            districts: [],
            cities: [],
            hospital_types: [],
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [open, state, district]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    let cancelled = false;
    setIsLoading(true);
    setLoadError("");
    searchPmjayHospitals({
      query,
      state,
      district,
      city,
      hospitalType,
      limit: 50,
    })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setHospitals(payload?.hospitals || []);
        setTotal(payload?.total || 0);
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        setLoadError(error.message || "Unable to load PM-JAY hospitals.");
        setHospitals([]);
        setTotal(0);
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [open, query, state, district, city, hospitalType]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const timer = window.setTimeout(() => searchRef.current?.focus(), 120);
    return () => window.clearTimeout(timer);
  }, [open]);

  const subtitle = useMemo(
    () =>
      total > hospitals.length
        ? `Showing ${hospitals.length} of ${total} hospitals`
        : `${total} hospital${total === 1 ? "" : "s"}`,
    [hospitals.length, total]
  );

  if (!open) {
    return null;
  }

  return createPortal(
    <div
      className="location-picker-overlay pmjay-hospitals-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="pmjay-hospitals-title"
      onClick={onClose}
    >
      <div
        className="location-picker-sheet pmjay-hospitals-sheet"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="location-picker-sheet-header pmjay-hospitals-header">
          <button
            type="button"
            className="location-picker-back"
            onClick={onClose}
            aria-label="Close PM-JAY hospital list"
          >
            ×
          </button>
          <div className="pmjay-hospitals-heading">
            <h2 id="pmjay-hospitals-title">PM-JAY Empanelled Hospitals</h2>
            <p className="pmjay-hospitals-subtitle">
              Search notified PM-JAY empanelled hospitals. Final empanelment and
              eligibility must still be verified officially.
            </p>
          </div>
        </header>

        <div className="pmjay-hospitals-filters">
          <div className="location-picker-sheet-search">
            <div className="location-picker-search-wrap">
              <SearchIcon />
              <input
                ref={searchRef}
                type="search"
                className="location-picker-search-input"
                placeholder="Search hospital, city, or district"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                aria-label="Search PM-JAY hospitals"
              />
            </div>
          </div>
          <div className="pmjay-hospitals-filter-row">
            <select
              value={state}
              onChange={(event) => {
                setState(event.target.value);
                setDistrict("");
                setCity("");
              }}
              aria-label="Filter by state"
            >
              <option value="">All states</option>
              {filters.states.map((option) => (
                <option key={option} value={option}>
                  {formatDisplayName(option)}
                </option>
              ))}
            </select>
            <select
              value={district}
              onChange={(event) => {
                setDistrict(event.target.value);
                setCity("");
              }}
              aria-label="Filter by district"
            >
              <option value="">All districts</option>
              {filters.districts.map((option) => (
                <option key={option} value={option}>
                  {formatDisplayName(option)}
                </option>
              ))}
            </select>
            <select
              value={city}
              onChange={(event) => setCity(event.target.value)}
              aria-label="Filter by city"
            >
              <option value="">All cities</option>
              {filters.cities.map((option) => (
                <option key={option} value={option}>
                  {formatDisplayName(option)}
                </option>
              ))}
            </select>
            <select
              value={hospitalType}
              onChange={(event) => setHospitalType(event.target.value)}
              aria-label="Filter by hospital type"
            >
              <option value="">All types</option>
              {filters.hospital_types.map((option) => (
                <option key={option} value={option}>
                  {formatDisplayName(option)}
                </option>
              ))}
            </select>
          </div>
          <p className="pmjay-hospitals-count">{subtitle}</p>
        </div>

        <div className="location-picker-sheet-list pmjay-hospitals-list pmjay-hospitals-list-v2">
          {isLoading && (
            <p className="location-picker-empty">Loading PM-JAY hospitals...</p>
          )}
          {!isLoading && loadError && (
            <p className="location-picker-empty">{loadError}</p>
          )}
          {!isLoading && !loadError && hospitals.length === 0 && (
            <p className="location-picker-empty">No hospitals match your search.</p>
          )}
          {!isLoading &&
            !loadError &&
            hospitals.map((hospital) => (
              <PmjayHospitalCard
                key={`${hospital.hospital_id}-${hospital.hospital_name}`}
                hospital={hospital}
              />
            ))}
        </div>
      </div>
    </div>,
    document.body
  );
}
