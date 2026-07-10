// Best-effort presentational heuristics over the engine's free-text
// assumptions[] strings (see economics.py build_assumptions). Coupled to the
// current Danish wording: if that copy changes, these silently stop
// matching and the affected line just loses its visual emphasis — it still
// renders in the full assumptions list either way.

export function hasSyntheticWarning(assumptions: string[]): string | null {
  return assumptions.find((a) => a.startsWith("ADVARSEL")) ?? null;
}

export function unverifiedNotes(assumptions: string[]): string[] {
  return assumptions.filter((a) => a.includes("ikke verificeret"));
}

export type AssumptionSeverity = "critical" | "warning" | "neutral";

export function assumptionSeverity(assumption: string): AssumptionSeverity {
  if (assumption.startsWith("ADVARSEL")) return "critical";
  if (assumption.includes("ikke verificeret")) return "warning";
  return "neutral";
}
