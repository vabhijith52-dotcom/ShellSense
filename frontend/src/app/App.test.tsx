import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { App } from "./App";

describe("App Scaffold", () => {
  it("renders the sidebar with branding and navigation tabs", () => {
    render(<App />);

    expect(screen.getAllByText("ShellSense").length).toBeGreaterThan(0);
    expect(screen.getByText("Natural Language OS Assistant")).toBeDefined();
    expect(screen.getByText("Chat")).toBeDefined();
    expect(screen.getByText("Tasks")).toBeDefined();
    expect(screen.getByText("System Monitor")).toBeDefined();
    expect(screen.getByText("File Operations")).toBeDefined();
    expect(screen.getByText("Process Manager")).toBeDefined();
    expect(screen.getByText("History")).toBeDefined();
    expect(screen.getByText("Settings")).toBeDefined();
  });

  it("renders the detected OS badge as display-only", () => {
    render(<App />);
    expect(screen.getAllByText("Auto (This System)").length).toBeGreaterThan(0);
  });
});
