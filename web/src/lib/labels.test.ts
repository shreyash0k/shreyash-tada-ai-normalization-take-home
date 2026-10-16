import { describe, expect, it } from "vitest";
import { fieldLabel, shortSource } from "./labels";

describe("fieldLabel", () => {
  it("drops the section and spaces out scalar names", () => {
    expect(fieldLabel("employment.status_date")).toBe("status date");
  });
  it("names list rows by kind", () => {
    expect(fieldLabel("contact.addresses[home]")).toBe("home address");
    expect(fieldLabel("contact.addresses[w2]")).toBe("W-2 address");
    expect(fieldLabel("contact.phones[mobile]")).toBe("mobile phone");
  });
  it("says when the provider did not state the kind", () => {
    expect(fieldLabel("contact.emails[unknown]")).toBe("email, kind not stated");
  });
  it("keeps top-level deposit fields whole", () => {
    expect(fieldLabel("bank_name")).toBe("bank name");
    expect(fieldLabel("allocation.method")).toBe("method");
  });
  it("spells out deposit rows that read badly on their own", () => {
    expect(fieldLabel("account_number_last4")).toBe("account number, last 4");
    expect(fieldLabel("effective.start")).toBe("effective start");
    expect(fieldLabel("effective.end")).toBe("effective end");
  });
  it("labels deduction rows", () => {
    expect(fieldLabel("code")).toBe("code");
    expect(fieldLabel("limits.per_pay")).toBe("per pay");
    expect(fieldLabel("employer_match.annual_max")).toBe("annual max");
    expect(fieldLabel("payee.id")).toBe("payee ID");
    expect(fieldLabel("payee.name")).toBe("payee name");
  });
});

describe("shortSource", () => {
  it("keeps a plain source path", () => {
    expect(shortSource("client.workEmail")).toBe("client.workEmail");
  });
  it("drops the lookup note after the first comma", () => {
    expect(shortSource("client.jobCode, named by GET /clientMaster/v1/getClientCodes")).toBe("client.jobCode");
  });
});
