import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ItemsPage from "@/app/(app)/items/page";
import { api } from "@/lib/api";
import { renderWithQuery } from "./utils";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: vi.fn(),
    push: vi.fn(),
  }),
  usePathname: () => "/items",
}));

describe("ItemsPage", () => {
  beforeEach(() => {
    localStorage.clear();
    delete process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID;
    vi.spyOn(api, "listItems").mockResolvedValue({ items: [], total: 0 });
  });

  it("renders the item board cleanly when Cognito is not configured", async () => {
    delete process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID;
    renderWithQuery(<ItemsPage />);

    await waitFor(() => {
      expect(screen.getByRole("region", { name: "To do" })).toBeInTheDocument();
      expect(
        screen.getByRole("region", { name: "In progress" }),
      ).toBeInTheDocument();
      expect(screen.getByRole("region", { name: "Done" })).toBeInTheDocument();
    });

    expect(screen.queryByText("Could not load tasks")).not.toBeInTheDocument();
  });
});
