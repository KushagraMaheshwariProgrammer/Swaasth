import { useState } from "react";
import TermsAndConditionsModal from "../components/TermsAndConditionsModal";

export default function TermsDevPreview() {
  const [accepted, setAccepted] = useState(false);
  const [message, setMessage] = useState("");

  if (accepted) {
    return (
      <main className="auth-wrap">
        <section className="auth-card">
          <h1>Terms accepted</h1>
          <p className="auth-info">{message}</p>
          <button
            type="button"
            className="analyze-btn"
            onClick={() => {
              setAccepted(false);
              setMessage("");
            }}
          >
            Show modal again
          </button>
        </section>
      </main>
    );
  }

  return (
    <TermsAndConditionsModal
      onAccept={() => {
        setMessage("Accept handler fired.");
        setAccepted(true);
      }}
      onDecline={() => {
        setMessage("Decline handler fired.");
        setAccepted(true);
      }}
    />
  );
}
