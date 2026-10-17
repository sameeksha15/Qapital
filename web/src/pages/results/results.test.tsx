import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import saved from "../../../public/saved/results/nifty50-default.json";
import type { JobStatus } from "../../api/types";
import { OrdersSection } from "./OrdersSection";

// A real saved run (scripts/build_saved_site.py), so the test reads exactly what the API sends.
const result = (saved as unknown as JobStatus).result!;

describe("orders and costs", () => {
  it("lists every order with its charges, and switches to the lowest-risk split", async () => {
    render(<OrdersSection result={result} currency="INR" />);
    const equal = result.allocations!.find((a) => a.sizing === "equal")!;
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(1 + equal.orders.length);

    const first = equal.orders[0];
    await userEvent.click(within(table).getAllByRole("button", { expanded: false })[0]);
    for (const line of first.costs) expect(screen.getByText(line.name)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("radio", { name: "Lowest-risk split" }));
    expect(screen.getByText(/swing least/)).toBeInTheDocument();
  });
});
