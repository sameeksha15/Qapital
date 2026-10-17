import { expect, test } from "@playwright/test";

// A real run through the live API: pick a few stocks, run, follow the progress, land on the result.
test.skip(!process.env.E2E_API_URL, "set E2E_API_URL to run against a live API");

test("a small optimisation runs end to end", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto("/");
  await expect(page.getByText("Live engine", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Clear" }).click();
  for (const ticker of ["HDFCBANK", "INFY", "SUNPHARMA", "LT", "NTPC", "TITAN"]) {
    await page.getByRole("button", { name: ticker, exact: true }).click();
  }
  await page.getByRole("button", { name: "Fewer: Stocks to buy" }).click();
  await page.getByRole("button", { name: "Fewer: Stocks to buy" }).click();
  await page.getByRole("button", { name: /Run optimisation/ }).click();
  await expect(page).toHaveURL(/\/runs\//);
  await expect(page).toHaveURL(/\/results\/[0-9a-f]{32}$/, { timeout: 150_000 });
  await expect(page.getByRole("heading", { name: "Orders and costs" })).toBeVisible();
  await expect(page.getByText("2 of 6 stocks").or(page.getByText(/6 stocks/)).first()).toBeVisible();
});
