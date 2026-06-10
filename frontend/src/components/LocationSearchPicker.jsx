import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

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

const MAX_VISIBLE_RESULTS = 200;

export default function LocationSearchPicker({
  label,
  items = [],
  value = "",
  onSelect,
  disabled = false,
  isLoading = false,
  loadingLabel = "Loading...",
  emptyLabel = "No options available",
  placeholder = "Select",
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const searchRef = useRef(null);

  const filteredItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) {
      return items;
    }
    return items.filter((item) => item.toLowerCase().includes(normalizedQuery));
  }, [items, query]);

  const visibleItems = filteredItems.slice(0, MAX_VISIBLE_RESULTS);

  const closePicker = () => {
    setOpen(false);
    setQuery("");
  };

  const openPicker = () => {
    if (disabled || isLoading) {
      return;
    }
    setQuery("");
    setOpen(true);
  };

  const handleSelect = (nextValue) => {
    onSelect(nextValue);
    closePicker();
  };

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        closePicker();
      }
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleKeyDown);
    const focusTimer = window.setTimeout(() => {
      searchRef.current?.focus();
    }, 50);

    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  const triggerText = isLoading
    ? loadingLabel
    : value || (disabled ? emptyLabel : placeholder);

  const listContent = (() => {
    if (isLoading) {
      return <p className="location-picker-empty">{loadingLabel}</p>;
    }
    if (items.length === 0) {
      return <p className="location-picker-empty">{emptyLabel}</p>;
    }
    if (visibleItems.length === 0) {
      return <p className="location-picker-empty">No results found</p>;
    }
    return (
      <>
        {visibleItems.map((item) => (
          <button
            key={item}
            type="button"
            role="option"
            aria-selected={item === value}
            className={`location-picker-option${
              item === value ? " is-selected" : ""
            }`}
            onClick={() => handleSelect(item)}
          >
            <span>{item}</span>
            {item === value && (
              <span className="location-picker-check" aria-hidden="true">
                ✓
              </span>
            )}
          </button>
        ))}
        {filteredItems.length > MAX_VISIBLE_RESULTS && (
          <p className="location-picker-empty location-search-more">
            Showing first {MAX_VISIBLE_RESULTS} matches. Keep typing to narrow
            down.
          </p>
        )}
      </>
    );
  })();

  return (
    <>
      <label className="setting-field location-picker-field">
        <span>{label}</span>
        <button
          type="button"
          className={`location-picker-trigger${
            !value && !isLoading ? " is-placeholder" : ""
          }${disabled || isLoading ? " is-disabled" : ""}`}
          onClick={openPicker}
          disabled={disabled || isLoading}
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-label={`${label}: ${triggerText}`}
        >
          <span className="location-picker-trigger-text">{triggerText}</span>
          <span className="location-picker-chevron" aria-hidden="true">
            ›
          </span>
        </button>
      </label>

      {open &&
        createPortal(
          <div
            className="location-picker-overlay"
            role="presentation"
            onClick={closePicker}
          >
            <div
              className="location-picker-sheet"
              role="dialog"
              aria-modal="true"
              aria-label={label}
              onClick={(event) => event.stopPropagation()}
            >
              <header className="location-picker-sheet-header">
                <button
                  type="button"
                  className="location-picker-back"
                  onClick={closePicker}
                  aria-label="Close"
                >
                  ‹
                </button>
                <h2 className="location-picker-sheet-title">{label}</h2>
              </header>

              <div className="location-picker-sheet-search">
                <div className="location-picker-search-wrap">
                  <SearchIcon />
                  <input
                    ref={searchRef}
                    type="search"
                    className="location-picker-search-input"
                    placeholder="Search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    autoComplete="off"
                    enterKeyHint="search"
                    aria-label={`Search ${label}`}
                  />
                </div>
              </div>

              <div
                className="location-picker-sheet-list"
                role="listbox"
                aria-label={label}
              >
                {listContent}
              </div>
            </div>
          </div>,
          document.body
        )}
    </>
  );
}
