import { describe, expect, it } from "vitest";
import { fieldLabel } from "./labels";

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
});
