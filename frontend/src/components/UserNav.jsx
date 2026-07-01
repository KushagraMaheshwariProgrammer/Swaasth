import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const BASE_NAV_LINKS = [
  { to: "/patients", label: "Patients" },
  { to: "/history", label: "Past bills", requiresHistoryConsent: true },
  { to: "/account", label: "Account" },
];

function getUserInitial(user) {
  const source =
    user?.displayName?.trim() ||
    user?.email?.trim() ||
    user?.email?.split("@")[0]?.trim() ||
    "?";
  return source.charAt(0).toUpperCase();
}

function useIsMobileNav() {
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === "undefined") return true;
    return window.matchMedia("(max-width: 859px)").matches;
  });

  useEffect(() => {
    const media = window.matchMedia("(max-width: 859px)");
    const sync = () => setIsMobile(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  return isMobile;
}

export default function UserNav({ className = "" }) {
  const { user, logOut, loading, medicalHistoryConsentAccepted } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuStyle, setMenuStyle] = useState({});
  const location = useLocation();
  const navRef = useRef(null);
  const menuRef = useRef(null);
  const avatarRef = useRef(null);
  const isMobileNav = useIsMobileNav();

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!menuOpen || !avatarRef.current || isMobileNav) {
      setMenuStyle({});
      return undefined;
    }

    const updatePosition = () => {
      const rect = avatarRef.current?.getBoundingClientRect();
      if (!rect) return;
      setMenuStyle({
        top: rect.bottom + 10,
        right: Math.max(12, window.innerWidth - rect.right),
      });
    };

    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [menuOpen, isMobileNav]);

  useEffect(() => {
    if (!menuOpen) return undefined;

    const handlePointerDown = (event) => {
      const target = event.target;
      const inTrigger = navRef.current?.contains(target);
      const inMenu = menuRef.current?.contains(target);
      if (!inTrigger && !inMenu) {
        setMenuOpen(false);
      }
    };
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    if (isMobileNav) {
      document.body.style.overflow = "hidden";
    }

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [menuOpen, isMobileNav]);

  if (loading) {
    return null;
  }

  if (!user) {
    return (
      <div className={`user-nav ${className}`.trim()} ref={navRef}>
        <Link to="/login" className="user-nav-cta">
          Sign in
        </Link>
      </div>
    );
  }

  const email = user.email || "Signed in";
  const initial = getUserInitial(user);
  const navLinks = BASE_NAV_LINKS.filter(
    (link) =>
      !link.requiresHistoryConsent || Boolean(medicalHistoryConsentAccepted)
  );

  const accountMenu = (
    <AnimatePresence>
      {menuOpen && (
        <>
          <motion.button
            type="button"
            className="user-nav-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            aria-label="Close account menu"
            onClick={() => setMenuOpen(false)}
          />
          <motion.div
            id="user-account-menu"
            ref={menuRef}
            className={`user-account-menu${isMobileNav ? " is-sheet" : " is-popover"}`}
            style={isMobileNav ? undefined : menuStyle}
            role="dialog"
            aria-modal="true"
            aria-label="Account menu"
            initial={{ opacity: 0, y: isMobileNav ? 24 : 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: isMobileNav ? 24 : 8 }}
            transition={{ type: "tween", duration: 0.22, ease: "easeOut" }}
          >
            <div className="user-account-menu-header">
              <div className="user-account-menu-identity">
                <span className="user-account-menu-avatar" aria-hidden="true">
                  {initial}
                </span>
                <div className="user-account-menu-meta">
                  <p className="user-account-menu-status">Signed in</p>
                  <p className="user-account-menu-email">{email}</p>
                  <p className="user-account-menu-label">Account</p>
                </div>
              </div>
            </div>

            <div className="user-account-menu-links">
              {navLinks.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  className="user-account-menu-link"
                >
                  {link.label}
                </Link>
              ))}
            </div>

            <button
              type="button"
              className="user-account-menu-signout"
              onClick={() => logOut()}
            >
              Sign out
            </button>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );

  return (
    <>
      <nav
        className={`user-nav ${className}`.trim()}
        ref={navRef}
        aria-label="Account navigation"
      >
        <div className="user-nav-desktop" aria-label="Main navigation">
          {navLinks.map((link) => (
            <Link key={link.to} to={link.to} className="user-nav-link">
              {link.label}
            </Link>
          ))}
        </div>

        <button
          type="button"
          ref={avatarRef}
          className={`user-nav-avatar${menuOpen ? " is-open" : ""}`}
          aria-expanded={menuOpen}
          aria-controls="user-account-menu"
          aria-label="Open account menu"
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span className="user-nav-avatar-letter" aria-hidden="true">
            {initial}
          </span>
        </button>
      </nav>

      {typeof document !== "undefined" &&
        createPortal(accountMenu, document.body)}
    </>
  );
}
