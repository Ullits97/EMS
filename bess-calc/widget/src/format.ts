export const dkk = (v: number): string => `${Math.round(v).toLocaleString("da-DK")} kr.`;

export const years = (v: number): string =>
  v.toLocaleString("da-DK", { maximumFractionDigits: 1 });

export function dkkInterval(low: number, high: number): string {
  const l = Math.round(low);
  const h = Math.round(high);
  if (Math.abs(h - l) < 50) return dkk(l);
  return `${dkk(l)} – ${dkk(h)}`;
}

export function paybackYearsText(
  low: number | null,
  high: number | null,
  neverText: string,
): string {
  if (low == null && high == null) return neverText;
  if (low != null && high != null) {
    return Math.abs(high - low) < 0.3 ? `ca. ${years(low)} år` : `${years(low)}–${years(high)} år`;
  }
  return `${years((low ?? high) as number)} år eller mere`;
}
