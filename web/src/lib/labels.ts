const LIST_NOUN: Record<string, string> = { addresses: "address", phones: "phone", emails: "email" };

export function fieldLabel(field: string): string {
  const name = field.slice(field.indexOf(".") + 1);
  const list = name.match(/^(addresses|phones|emails)\[(\w+)\]$/);
  if (list) {
    const noun = LIST_NOUN[list[1]];
    if (list[2] === "unknown") return `${noun}, kind not stated`;
    return `${list[2] === "w2" ? "W-2" : list[2]} ${noun}`;
  }
  return name.replaceAll("_", " ");
}

export function shortSource(source: string): string {
  const comma = source.indexOf(", ");
  return comma === -1 ? source : source.slice(0, comma);
}
