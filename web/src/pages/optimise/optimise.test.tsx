import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import markets from "../../../public/saved/markets.json";
import runs from "../../../public/saved/runs.json";
import nifty from "../../../public/saved/stocks/nifty50.json";
import sp100 from "../../../public/saved/stocks/sp100.json";
import { ConnectionProvider } from "../../api/connection";
import { DraftProvider } from "../../state/draft";
import { OptimisePage } from "./OptimisePage";

vi.mock("../../components/charts/MarketMap", () => ({ MarketMap: () => <div data-testid="market-map" /> }));

const FILES: Record<string, unknown> = {
  "markets.json": markets, "runs.json": runs, "stocks/nifty50.json": nifty, "stocks/sp100.json": sp100,
};

function renderPage() {
  const router = createMemoryRouter([{ path: "/", element: <OptimisePage /> }]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ConnectionProvider apiUrl={undefined}>
        <DraftProvider><RouterProvider router={router} /></DraftProvider>
      </ConnectionProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  sessionStorage.clear();
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const file = Object.keys(FILES).find((name) => url.endsWith(name));
    return file ? new Response(JSON.stringify(FILES[file]), { headers: { "Content-Type": "application/json" } }) : new Response("", { status: 404 });
  }));
});

afterEach(() => vi.unstubAllGlobals());

describe("the optimiser without a live engine", () => {
  it("shows the market, keeps Run off, and offers the saved runs", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: /Pick a few stocks/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Run optimisation/ })).toBeDisabled();
    expect(screen.getByText("Saved runs only")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /NIFTY 50, four stocks/ })).toHaveAttribute("href", "/results/nifty50-default");
  });

  it("switches market, with that market's currency and money", async () => {
    renderPage();
    await userEvent.click(await screen.findByRole("radio", { name: /S&P 100/ }));
    expect(await screen.findByText("Amounts in USD", { exact: false })).toBeInTheDocument();
    expect(screen.getAllByText("$100,000").length).toBeGreaterThan(0);
  });

  it("explains a list that is too short", async () => {
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Clear" }));
    expect(screen.getByText("Pick at least 2 stocks.")).toBeInTheDocument();
  });
});
