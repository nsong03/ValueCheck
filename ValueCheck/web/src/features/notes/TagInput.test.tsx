import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TagInput } from "./TagInput";

afterEach(cleanup);

const VOCAB = ["semiconductors", "hardware", "wide-moat", "saas", "energy"];

describe("TagInput fuzzy suggest", () => {
  it("suggests despite typos (fuse.js)", () => {
    render(<TagInput value={[]} onChange={() => {}} vocabulary={VOCAB} />);
    fireEvent.change(screen.getByLabelText("Add tag"), {
      target: { value: "semicondctors" }, // missing 'u'
    });
    const listbox = screen.getByRole("listbox");
    expect(listbox.textContent).toContain("semiconductors");
  });

  it("clicking a suggestion adds the canonical vocabulary tag", () => {
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} vocabulary={VOCAB} />);
    fireEvent.change(screen.getByLabelText("Add tag"), { target: { value: "hardwre" } });
    fireEvent.click(screen.getByRole("option", { name: "hardware" }));
    expect(onChange).toHaveBeenCalledWith(["hardware"]);
  });

  it("enter adds best suggestion; enter with exact text keeps user text", () => {
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} vocabulary={VOCAB} />);
    const input = screen.getByLabelText("Add tag");
    fireEvent.change(input, { target: { value: "wide-mot" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(["wide-moat"]); // typo corrected

    const onChange2 = vi.fn();
    cleanup();
    render(<TagInput value={[]} onChange={onChange2} vocabulary={VOCAB} />);
    const input2 = screen.getByLabelText("Add tag");
    fireEvent.change(input2, { target: { value: "brand-new-tag" } });
    fireEvent.keyDown(input2, { key: "Enter" });
    expect(onChange2).toHaveBeenCalledWith(["brand-new-tag"]); // novel tag allowed
  });

  it("already-selected tags are not re-suggested", () => {
    render(<TagInput value={["hardware"]} onChange={() => {}} vocabulary={VOCAB} />);
    fireEvent.change(screen.getByLabelText("Add tag"), { target: { value: "hardware" } });
    expect(screen.queryByRole("option", { name: "hardware" })).toBeNull();
  });

  it("chips can be removed", () => {
    const onChange = vi.fn();
    render(<TagInput value={["a", "b"]} onChange={onChange} vocabulary={[]} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove tag a" }));
    expect(onChange).toHaveBeenCalledWith(["b"]);
  });
});
