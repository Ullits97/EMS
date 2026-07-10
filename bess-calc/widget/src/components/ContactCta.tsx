import type { Branding } from "../types";

interface Props {
  branding: Branding;
}

export function ContactCta({ branding }: Props) {
  const { contact_phone, contact_email, cta_text, cta_url } = branding;
  const hasContact = Boolean(contact_phone || contact_email);
  const hasCta = Boolean(cta_text && cta_url);
  if (!hasContact && !hasCta) return null;

  return (
    <div className="bc-contact-cta">
      {hasContact ? (
        <p className="bc-hint">
          Kontakt {branding.name}
          {contact_phone ? ` · ${contact_phone}` : ""}
          {contact_email ? ` · ${contact_email}` : ""}
        </p>
      ) : null}
      {hasCta ? (
        <a className="bc-button bc-cta-button" href={cta_url ?? undefined}>
          {cta_text}
        </a>
      ) : null}
    </div>
  );
}
