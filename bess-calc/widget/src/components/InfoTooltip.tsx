import { useEffect, useRef, useState } from "react";

interface Props {
  id: string;
  label: string;
  children: React.ReactNode;
}

export function InfoTooltip({ id, label, children }: Props) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLSpanElement>(null);
  const panelId = `${id}-panel`;

  useEffect(() => {
    if (!open) return;

    function onDocClick(e: MouseEvent): void {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(e: KeyboardEvent): void {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("click", onDocClick);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("click", onDocClick);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <span className="bc-info-wrap" ref={wrapRef}>
      <button
        type="button"
        id={id}
        className="bc-info-btn"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={label}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
      >
        i
      </button>
      {open ? (
        <span id={panelId} className="bc-info-panel" role="note">
          {children}
        </span>
      ) : null}
    </span>
  );
}
