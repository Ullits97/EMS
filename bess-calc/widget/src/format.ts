export const dkk = (v: number): string => `${Math.round(v).toLocaleString("da-DK")} kr.`;

export const years = (v: number): string =>
  v.toLocaleString("da-DK", { maximumFractionDigits: 1 });
