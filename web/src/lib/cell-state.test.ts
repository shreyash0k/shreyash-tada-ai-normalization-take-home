import { describe, expect, it } from "vitest";
import { cellState } from "./cell-state";
import type { FieldStatus } from "./data";

const entry = (status: FieldStatus, filled: number, total = 6) => ({ status, filled, total });

describe("cellState", () => {
  it("is filled when every employee has the field", () => {
    expect(cellState(entry("mapped", 6))).toBe("filled");
  });
  it("is partial when only some employees have it", () => {
    expect(cellState(entry("mapped", 1))).toBe("partial");
    expect(cellState(entry("mapped", 5))).toBe("partial");
  });
  it("is empty in sample when a mapped field is never filled", () => {
    expect(cellState(entry("mapped", 0))).toBe("empty_in_sample");
    expect(cellState(entry("mapped", 0, 0))).toBe("empty_in_sample");
  });
  it("reports not mapped yet and not offered regardless of counts", () => {
    expect(cellState(entry("not_mapped_yet", 0))).toBe("not_mapped_yet");
    expect(cellState(entry("not_offered", 0))).toBe("not_offered");
  });
});
