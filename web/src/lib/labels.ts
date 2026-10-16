const LIST_NOUN: Record<string, string> = { addresses: "address", phones: "phone", emails: "email" };

const LABEL_OVERRIDES: Record<string, string> = {
  account_number_last4: "account number, last 4",
  "effective.start": "effective start",
  "effective.end": "effective end",
  "payee.id": "payee ID",
  "payee.name": "payee name",
  "pay_run.period.start": "period start",
  "pay_run.period.end": "period end",
  "paycheck.period.start": "period start",
  "paycheck.period.end": "period end",
  "payments.account_last4": "account, last 4",
  "company.ein": "EIN",
  "company.naics_code": "NAICS code",
  "company.sic_code": "SIC code",
  "tax_ids.tax_id": "tax ID",
  "pay_groups.effective.start": "effective start",
  "pay_groups.effective.end": "effective end",
};

export function fieldLabel(field: string): string {
  if (field in LABEL_OVERRIDES) return LABEL_OVERRIDES[field];
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
