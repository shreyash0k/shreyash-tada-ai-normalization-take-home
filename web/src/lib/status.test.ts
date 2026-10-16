import { describe, expect, it } from "vitest";
import { STATUSES, STATUS_DESCRIPTION, STATUS_LABEL } from "./status";

describe("status copy", () => {
  it("gives every status a label and a description", () => {
    for (const status of STATUSES) {
      expect(STATUS_LABEL[status].length).toBeGreaterThan(0);
      expect(STATUS_DESCRIPTION[status].length).toBeGreaterThan(0);
    }
  });
});
