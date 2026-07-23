import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { NoteOut } from "../../api/client";
import { NoteEditor } from "./NoteEditor";

afterEach(cleanup);

const EXISTING: NoteOut = {
  id: 7,
  ticker: "DEMO",
  reference_id: null,
  analysis_id: null,
  title: "Thesis",
  body: "Sticky ecosystem.",
  tags: ["wide-moat"],
  links: [],
  created_at: "2026-07-22T00:00:00Z",
  updated_at: "2026-07-22T00:00:00Z",
};

describe("NoteEditor", () => {
  it("submits title, body, and tags", () => {
    const onSave = vi.fn();
    render(
      <NoteEditor
        initial={null}
        vocabulary={[]}
        onSave={onSave}
        onCancel={() => {}}
        saving={false}
      />,
    );
    fireEvent.change(screen.getByLabelText("Note title"), { target: { value: "  My note  " } });
    fireEvent.change(screen.getByLabelText("Note body"), { target: { value: "Body text" } });
    const tagInput = screen.getByLabelText("Add tag");
    fireEvent.change(tagInput, { target: { value: "Wide Moat" } });
    fireEvent.keyDown(tagInput, { key: "Enter" });
    fireEvent.click(screen.getByRole("button", { name: "Add note" }));

    expect(onSave).toHaveBeenCalledWith({
      title: "My note",
      body: "Body text",
      tags: ["Wide Moat"], // raw — the SERVER canonicalizes on save
      links: [],
    });
  });

  it("adds and removes inline links", () => {
    const onSave = vi.fn();
    render(
      <NoteEditor
        initial={null}
        vocabulary={[]}
        onSave={onSave}
        onCancel={() => {}}
        saving={false}
      />,
    );
    fireEvent.change(screen.getByLabelText("Note title"), { target: { value: "t" } });
    fireEvent.change(screen.getByLabelText("Link label"), {
      target: { value: "Damodaran on WACC" },
    });
    fireEvent.change(screen.getByLabelText("Link URL"), {
      target: { value: "https://example.com/wacc" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add link" }));
    expect(screen.getByText("Damodaran on WACC")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Add note" }));
    expect(onSave).toHaveBeenCalledWith({
      title: "t",
      body: "",
      tags: [],
      links: [{ label: "Damodaran on WACC", url: "https://example.com/wacc" }],
    });
  });

  it("prefills when editing an existing note", () => {
    render(
      <NoteEditor
        initial={EXISTING}
        vocabulary={[]}
        onSave={() => {}}
        onCancel={() => {}}
        saving={false}
      />,
    );
    expect((screen.getByLabelText("Note title") as HTMLInputElement).value).toBe("Thesis");
    expect(screen.getByText("wide-moat")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeTruthy();
  });

  it("blocks empty titles", () => {
    const onSave = vi.fn();
    render(
      <NoteEditor
        initial={null}
        vocabulary={[]}
        onSave={onSave}
        onCancel={() => {}}
        saving={false}
      />,
    );
    const submit = screen.getByRole("button", { name: "Add note" });
    expect((submit as HTMLButtonElement).disabled).toBe(true);
  });
});
