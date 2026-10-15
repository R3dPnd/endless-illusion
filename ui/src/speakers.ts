/**
 * Chat identities for the Original Seven, colored after their Gun x Sword
 * armors / pilots and pushed to the arcade neon palette shared with
 * dann-of-thursday. Where the source gives no clear color the pick is
 * interpretive (noted inline).
 */
export interface Speaker {
  id: string;
  name: string;
  color: string;
  source: string;
}

export const SPEAKERS: Record<string, Speaker> = {
  "saudade-of-sunday": {
    id: "saudade-of-sunday",
    name: "Saudade",
    color: "#ffdd00", // golden pistol form (Michael)
    source: "Saudade of Sunday · Michael",
  },
  "diablo-of-monday": {
    id: "diablo-of-monday",
    name: "Diablo",
    color: "#ff5533", // "devil" + Gadved's axe — interpretive ember red
    source: "Diablo of Monday · Gadved",
  },
  "metsa-of-tuesday": {
    id: "metsa-of-tuesday",
    name: "Metsä",
    color: "#00ff88", // metsä = "forest" (Wu)
    source: "Metsä of Tuesday · Wu",
  },
  "dahlia-of-wednesday": {
    id: "dahlia-of-wednesday",
    name: "Dahlia",
    color: "#ff66cc", // pink-petalled dahlia, petal plates (Fasalina)
    source: "Dahlia of Wednesday · Fasalina",
  },
  "dann-of-thursday": {
    id: "dann-of-thursday",
    name: "Dann",
    color: "#00ffdd", // Dann's teal in dann-of-thursday's own UI
    source: "Dann of Thursday · Van",
  },
  "sin-of-friday": {
    id: "sin-of-friday",
    name: "Sin",
    color: "#4488ff", // long blue spiked tail (Carossa)
    source: "Sin of Friday · Carossa",
  },
  "sen-of-saturday": {
    id: "sen-of-saturday",
    name: "Sen",
    color: "#bb77ff", // smallest, interlocks with Sin (Melissa) — interpretive violet
    source: "Sen of Saturday · Melissa",
  },
};

export const OPERATOR: Speaker = {
  id: "operator",
  name: "Operator",
  color: "#e8f1ff",
  source: "you",
};

export function speakerFor(id: string | undefined): Speaker {
  if (!id || id === OPERATOR.id) return OPERATOR;
  return (
    SPEAKERS[id] ?? { id, name: id, color: "#8b93a7", source: id }
  );
}
