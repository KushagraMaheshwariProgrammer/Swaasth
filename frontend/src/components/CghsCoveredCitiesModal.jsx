import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  fetchCghsCoveredCities,
  filterCghsCoveredCities,
} from "../services/cghsSchemes";
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

export default function CghsCoveredCitiesModal({
  open,
  onClose,
  onSelectCity,
}) {
  const [cities, setCities] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [query, setQuery] = useState("");
  const [confirmCity, setConfirmCity] = useState(null);
  const searchRef = useRef(null);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setConfirmCity(null);
      return undefined;
    }

    let cancelled = false;
    setIsLoading(true);
    setLoadError("");

    fetchCghsCoveredCities()
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setCities(payload?.cities || []);
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        setLoadError(error.message || "Unable to load CGHS covered cities.");
        setCities([]);
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const timer = window.setTimeout(() => {
      searchRef.current?.focus();
    }, 120);
    return () => window.clearTimeout(timer);
  }, [open]);

  const filteredCities = useMemo(
    () => filterCghsCoveredCities(cities, query),
    [cities, query]
  );

  if (!open) {
    return null;
  }

  const handleConfirmSelection = () => {
    if (!confirmCity) {
      return;
    }
    onSelectCity?.(confirmCity);
    setConfirmCity(null);
    onClose();
  };

  return createPortal(
    <div
      className="location-picker-overlay cghs-covered-cities-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cghs-covered-cities-title"
      onClick={onClose}
    >
      <div
        className="location-picker-sheet cghs-covered-cities-sheet"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="location-picker-sheet-header cghs-covered-cities-header">
          <button
            type="button"
            className="location-picker-back"
            onClick={onClose}
            aria-label="Close CGHS covered cities list"
          >
            ×
          </button>
          <div className="cghs-covered-cities-heading">
            <h2 id="cghs-covered-cities-title">CGHS-Covered Cities</h2>
            <p className="cghs-covered-cities-subtitle">
              Select Yes if the patient resides in one of these notified
              CGHS-covered cities. Final eligibility must still be verified with
              CGHS/MoHFW.
            </p>
          </div>
        </header>

        <div className="location-picker-sheet-search cghs-covered-cities-search-wrap">
          <div className="location-picker-search-wrap">
            <SearchIcon />
            <input
              ref={searchRef}
              type="search"
              className="location-picker-search-input"
              placeholder="Search city or alias"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              aria-label="Search CGHS covered cities"
            />
          </div>
        </div>

        <div className="location-picker-sheet-list cghs-covered-cities-list">
          {isLoading && (
            <p className="location-picker-empty">Loading covered cities...</p>
          )}
          {!isLoading && loadError && (
            <p className="location-picker-empty">{loadError}</p>
          )}
          {!isLoading && !loadError && filteredCities.length === 0 && (
            <p className="location-picker-empty">No cities match your search.</p>
          )}
          {!isLoading &&
            !loadError &&
            filteredCities.map((city) => (
              <button
                key={city.city_display_name}
                type="button"
                className="cghs-covered-city-card"
                onClick={() => setConfirmCity(city)}
              >
                <span className="cghs-covered-city-card-name">
                  {formatDisplayName(city.city_display_name)}
                </span>
              </button>
            ))}
        </div>

        {confirmCity && (
          <div className="cghs-covered-city-confirm">
            <p>
              Mark patient as residing in a CGHS-covered city (
              {formatDisplayName(confirmCity.city_display_name)})?
            </p>
            <div className="cghs-covered-city-confirm-actions">
              <button
                type="button"
                className="bill-editor-secondary"
                onClick={() => setConfirmCity(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="analyze-btn"
                onClick={handleConfirmSelection}
              >
                Yes, mark as covered
              </button>
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
