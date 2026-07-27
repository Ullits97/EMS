import { useState } from "react";
import type { LeadContact } from "../types";

interface Props {
  installerName: string;
  onSubmit: (contact: LeadContact) => Promise<void>;
}

export function LeadCaptureForm({ installerName, onSubmit }: Props) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const valid = Boolean(name.trim() || phone.trim() || email.trim());

  async function handleSubmit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    if (!valid || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        name: name.trim() || undefined,
        phone: phone.trim() || undefined,
        email: email.trim() || undefined,
      });
      setSubmitted(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div className="bc-lead-form">
        <p className="bc-hint">Tak! {installerName} kontakter dig snart.</p>
      </div>
    );
  }

  return (
    <form className="bc-lead-form" onSubmit={handleSubmit}>
      <h4 className="bc-section-title">Vil du kontaktes om et tilbud?</h4>
      <div className="bc-row">
        <div className="bc-field">
          <label className="bc-label" htmlFor="bc-lead-name">
            Navn
          </label>
          <input
            id="bc-lead-name"
            className="bc-input"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="bc-field">
          <label className="bc-label" htmlFor="bc-lead-phone">
            Telefon
          </label>
          <input
            id="bc-lead-phone"
            className="bc-input"
            inputMode="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </div>
      </div>
      <div className="bc-field">
        <label className="bc-label" htmlFor="bc-lead-email">
          Email
        </label>
        <input
          id="bc-lead-email"
          className="bc-input"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      {error ? <p className="bc-error">{error}</p> : null}
      <p className="bc-hint">
        Ved at sende accepterer du at {installerName} kontakter dig baseret på disse
        oplysninger.
      </p>
      <button className="bc-button" type="submit" disabled={!valid || submitting}>
        {submitting ? "Sender…" : "Send mine oplysninger"}
      </button>
    </form>
  );
}
