// Coarse postnummer -> (DSO, price area) mapping for the demo.
// TODO refine: use the official DSO supply-area register in Phase 2.

export interface SiteMapping {
  dso: "n1" | "radius" | "cerius";
  price_area: "DK1" | "DK2";
  label: string;
}

export function mapPostcode(postcode: number): SiteMapping | null {
  if (postcode >= 1000 && postcode <= 3699) {
    return { dso: "radius", price_area: "DK2", label: "Radius (Storkøbenhavn/Nordsjælland)" };
  }
  if (postcode >= 3700 && postcode <= 3799) {
    // Bornholm: DK2; Trefor El-net Øst is not in the MVP catalog — approximate with Cerius.
    return { dso: "cerius", price_area: "DK2", label: "Cerius (tilnærmet, Bornholm)" };
  }
  if (postcode >= 4000 && postcode <= 4999) {
    return { dso: "cerius", price_area: "DK2", label: "Cerius (Sjælland/Lolland-Falster)" };
  }
  if (postcode >= 5000 && postcode <= 9999) {
    return { dso: "n1", price_area: "DK1", label: "N1 (Jylland/Fyn, tilnærmet)" };
  }
  return null;
}
