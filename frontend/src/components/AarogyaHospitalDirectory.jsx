import { useCallback, useEffect, useRef, useState } from "react";
import {
  getDistricts,
  getSpecialities,
  searchHospitals,
} from "../services/aarogyaBhadratha";

const PAGE_SIZE = 15;

export default function AarogyaHospitalDirectory({
  onSelect = null,
  selectLabel = "Select this hospital",
  initialDistrict = "",
}) {
  const [query, setQuery] = useState("");
  const [district, setDistrict] = useState(initialDistrict);
  const [speciality, setSpeciality] = useState("");
  const [districts, setDistricts] = useState([]);
  const [specialities, setSpecialities] = useState([]);

  const [hospitals, setHospitals] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const requestIdRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [districtList, specialityList] = await Promise.all([
          getDistricts(),
          getSpecialities(),
        ]);
        if (!cancelled) {
          setDistricts(districtList || []);
          setSpecialities(specialityList || []);
        }
      } catch {
        // Filters are optional; ignore load failure.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const runSearch = useCallback(
    async (nextPage, { append } = { append: false }) => {
      const requestId = ++requestIdRef.current;
      setLoading(true);
      setError("");
      try {
        const result = await searchHospitals({
          query,
          district,
          speciality,
          page: nextPage,
          limit: PAGE_SIZE,
        });
        if (requestId !== requestIdRef.current) {
          return;
        }
        setTotal(result.total || 0);
        setHasMore(Boolean(result.has_more));
        setPage(nextPage);
        setHospitals((prev) =>
          append ? [...prev, ...(result.results || [])] : result.results || []
        );
      } catch (err) {
        if (requestId === requestIdRef.current) {
          setError(
            err.message ||
              "Could not load Aarogya Bhadratha hospitals. Check your connection and try again."
          );
        }
      } finally {
        if (requestId === requestIdRef.current) {
          setLoading(false);
        }
      }
    },
    [query, district, speciality]
  );

  // Debounce filter changes so we don't fire a request per keystroke.
  useEffect(() => {
    const handle = window.setTimeout(() => {
      runSearch(1, { append: false });
    }, 350);
    return () => window.clearTimeout(handle);
  }, [runSearch]);

  const clearFilters = () => {
    setQuery("");
    setDistrict("");
    setSpeciality("");
  };

  const hasFilters = Boolean(query || district || speciality);

  return (
    <div className="abh-directory">
      <div className="abh-search-bar">
        <input
          type="search"
          className="abh-search-input"
          placeholder="Search by hospital, district, address or speciality"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Search Aarogya Bhadratha hospitals"
        />
      </div>
      <div className="abh-filter-row">
        <label className="setting-field">
          <span>District</span>
          <select value={district} onChange={(event) => setDistrict(event.target.value)}>
            <option value="">All districts</option>
            {districts.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label className="setting-field">
          <span>Speciality</span>
          <select
            value={speciality}
            onChange={(event) => setSpeciality(event.target.value)}
          >
            <option value="">All specialities</option>
            {specialities.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="abh-directory-meta">
        <span className="abh-result-count">
          {loading && !hospitals.length
            ? "Searching…"
            : `${total} hospital${total === 1 ? "" : "s"} found`}
        </span>
        {hasFilters && (
          <button type="button" className="abh-clear-filters" onClick={clearFilters}>
            Clear Filters
          </button>
        )}
      </div>

      {error && <p className="error-text">{error}</p>}

      {!loading && !error && hospitals.length === 0 && (
        <p className="auth-info">
          No Aarogya Bhadratha hospitals were found for the selected district or
          search.
        </p>
      )}

      <ul className="abh-hospital-list">
        {hospitals.map((hospital) => (
          <li key={hospital.id} className="abh-hospital-card">
            <div className="abh-hospital-card-body">
              <strong>{hospital.name}</strong>
              <p className="abh-hospital-district">{hospital.district}</p>
              <p className="abh-hospital-address">{hospital.address}</p>
              <p className="abh-hospital-spec">
                {(hospital.specialities && hospital.specialities.slice(0, 4).join(", ")) ||
                  hospital.specialities_text ||
                  "Speciality not listed"}
              </p>
              <p className="abh-hospital-meta">
                {hospital.accreditation || "—"}
                {hospital.hospital_code ? ` · Code ${hospital.hospital_code}` : ` · Ref ${hospital.ref_no}`}
              </p>
            </div>
            {onSelect && (
              <button
                type="button"
                className="bill-editor-secondary abh-hospital-select"
                onClick={() => onSelect(hospital)}
              >
                {selectLabel}
              </button>
            )}
          </li>
        ))}
      </ul>

      {hasMore && (
        <button
          type="button"
          className="bill-editor-add abh-load-more"
          onClick={() => runSearch(page + 1, { append: true })}
          disabled={loading}
        >
          {loading ? "Loading…" : "Load more hospitals"}
        </button>
      )}
    </div>
  );
}
