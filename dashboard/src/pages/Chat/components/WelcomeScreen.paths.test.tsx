import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

it("keeps both welcome mascot images under the DSM base when switching", async () => {
  vi.stubEnv("BASE_URL", "/octop/");
  const { default: WelcomeScreen } = await import("./WelcomeScreen");
  vi.spyOn(Math, "random").mockReturnValue(0.75);

  render(<WelcomeScreen onPromptClick={() => {}} quickCards={[]} />);
  const mascot = screen.getByRole("button", { name: "Octop mascot" });
  expect(mascot).toHaveAttribute("src", "/octop/octop-mascot-peek.webp");

  fireEvent.click(mascot);
  expect(mascot).toHaveAttribute("src", "/octop/octop-mascot-type.webp");
});
