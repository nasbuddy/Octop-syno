import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
});

it("prefixes bundled avatar previews and preset tiles once under the DSM base", async () => {
  vi.stubEnv("BASE_URL", "/octop/");
  const { ResourceAvatarPicker } = await import("./ResourceAvatarPicker");
  const onSelectPreset = vi.fn();
  const { container } = render(
    <ResourceAvatarPicker
      presets={[
        { id: "team-host", src: "/experts/avatars/team-host.svg" },
        {
          id: "team-lead",
          src: "/octop/experts/avatars/team-lead.svg",
        },
      ]}
      onSelectPreset={onSelectPreset}
    />,
  );

  expect(
    Array.from(container.querySelectorAll("img"), (image) =>
      image.getAttribute("src"),
    ),
  ).toEqual([
    "/octop/experts/avatars/team-host.svg",
    "/octop/experts/avatars/team-host.svg",
    "/octop/experts/avatars/team-lead.svg",
  ]);
  fireEvent.click(screen.getByRole("button", { name: "team-lead" }));
  expect(onSelectPreset).toHaveBeenCalledWith("team-lead");
});
