import { expect, test } from "@playwright/test";

// With no live engine the site must still work from the saved runs.
test.skip(Boolean(process.env.E2E_API_URL), "saved-mode tests run without a live API");

test("the optimiser loads both markets and offers saved runs @phone", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Pick a few stocks/ })).toBeVisible();
  await expect(page.getByRole("radio", { name: /NIFTY 50/ })).toBeVisible();
  await expect(page.getByRole("radio", { name: /S&P 100/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Run optimisation/ })).toBeDisabled();
  await expect(page.getByRole("link", { name: /NIFTY 50, four stocks/ })).toBeVisible();
  expect(errors).toEqual([]);
});

test("a saved result shows the portfolio, its orders and every method", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: /NIFTY 50, four stocks/ }).click();
  await expect(page).toHaveURL(/\/results\/nifty50-default$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("quantum circuit");
  await expect(page.getByRole("heading", { name: "Orders and costs" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Brute force" })).toBeVisible();
  await page.getByRole("radio", { name: "Lowest-risk split" }).click();
  await expect(page.getByText(/swing least/)).toBeVisible();

  await page.getByRole("link", { name: /History/ }).click();
  await expect(page.getByRole("link", { name: /NIFTY 50: 4 stocks/ })).toBeVisible();
});

test("a saved backtest shows the money over time and its caveats", async ({ page }) => {
  await page.goto("/backtest/sp100-backtest");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("$100,000");
  await expect(page.getByRole("heading", { name: "Side by side" })).toBeVisible();
  await expect(page.getByRole("cell", { name: /S&P 500 index/ })).toBeVisible();
  await expect(page.getByText(/survivorship bias/)).toBeVisible();
});

test("the data page shows the snapshot and correlations", async ({ page }) => {
  await page.goto("/data");
  await expect(page.getByRole("heading", { name: "The snapshot in use" })).toBeVisible();
  await expect(page.getByRole("img", { name: /moved together/ })).toBeVisible();
});

test("unknown addresses and results explain themselves", async ({ page }) => {
  await page.goto("/no-such-page");
  await expect(page.getByText("There's no page here")).toBeVisible();
  await page.goto("/results/not-a-real-id");
  await expect(page.getByText(/kept on the live server/)).toBeVisible();
});

test("old #page links still work", async ({ page }) => {
  await page.goto("/#research");
  await expect(page).toHaveURL(/\/research$/);
});

test("the research page shows every experiment from its saved files", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/research");
  for (const title of ["Fewer error-prone gates, or better answers?", "Quality per gate", "Tune for the best outcomes, not the average",
    "Warm start: a head start from the classical answer", "On a noisy IBM chip", "Pruning the risk model vs shrinking it"]) {
    await expect(page.getByRole("heading", { name: title })).toBeVisible();
  }
  await page.getByRole("radio", { name: "S&P 100" }).first().click();
  await expect(page.getByText(/problems/).first()).toBeVisible();
  expect(errors).toEqual([]);
});

test("how it works explains CVaR, warm start and mitigation with research numbers", async ({ page }) => {
  await page.goto("/how");
  await expect(page.getByRole("heading", { name: "Tune for the best shots (CVaR)" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Clean up the chip's mistakes/ })).toBeVisible();
  await page.getByRole("group", { name: "Warm start" }).getByRole("button", { name: /The fair comparison/ }).click();
  await expect(page.getByText(/The layers improved on their start in \d+ of \d+ problems/)).toBeVisible();
});
