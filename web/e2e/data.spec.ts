import { expect, test } from "@playwright/test";

test("manual record requires preview and persists only after Save", async ({
  page,
  request,
}) => {
  const key = `US:QA${Date.now()}`;
  const ticker = key.split(":")[1];
  await page.goto("/data");
  await page.getByRole("button", { name: "Add company", exact: true }).click();
  const inputs: Record<string, string> = {
    "Record ID": `qa-${ticker}`,
    Ticker: ticker,
    "Company name": "QA Synthetic Software",
    Country: "US",
    Sector: "Information Technology",
    Industry: "Software",
    "Sub-industry": "Application Software",
    "Price currency": "USD",
    "Reporting currency": "USD",
    "Fiscal year end (MM-DD)": "12-31",
    "Price date": "2026-11-20",
    "Business description":
      "Synthetic cloud software for enterprise workflows.",
    "Share price (price currency)": "10",
    "Shares outstanding (millions)": "20",
    "Total debt": "30",
    Cash: "10",
    "Revenue (LTM)": "100",
    "EBITDA (LTM)": "20",
  };
  for (const [label, value] of Object.entries(inputs))
    await page.getByLabel(label, { exact: true }).fill(value);
  await page
    .getByRole("combobox", { name: "Reporting units", exact: true })
    .selectOption("millions");
  await expect(
    page.getByRole("button", { name: "Save to memory" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Preview addition" }).click();
  await expect(
    page.getByRole("heading", { name: "Preview result" }),
  ).toBeVisible();
  await expect(page.getByText("create", { exact: true })).toBeVisible();
  expect(
    (await request.get(`/api/companies/${encodeURIComponent(key)}`)).status(),
  ).toBe(404);
  await page.getByRole("button", { name: "Save to memory" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: `Saved ${key}` }),
  ).toBeVisible();
  const stored = await (
    await request.get(`/api/companies/${encodeURIComponent(key)}`)
  ).json();
  expect(stored.latest.original.net_income).toBeNull();
  expect(stored.metrics.pe.status).toBe("missing");
  expect(stored.metrics.enterprise_value_usd_m.display).toBe("220.0");
});

test("Data filters findings and companies and opens observation provenance", async ({
  page,
}) => {
  await page.goto("/data");
  const findings = page.getByRole("region", { name: "Findings", exact: true });
  await page.getByLabel("Finding company key", { exact: true }).fill("US:ORBT");
  await expect(
    findings.getByText("model-derived", { exact: true }),
  ).toBeVisible();
  await expect(findings.getByText("US:ORBT", { exact: true })).toBeVisible();
  await page.getByLabel("Search companies", { exact: true }).fill("US:NOMA");
  await page
    .getByRole("button", { name: /Noma Cloud Systems.*US:NOMA$/ })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Aliases" })).toBeVisible();
  await expect(
    dialog.getByText("Noma Software, Noma Cloud Systems", { exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("heading", { name: "Observation history" }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Close panel" }).click();
  await page.getByRole("button", { name: "Switch to dark mode" }).click();
  await expect(page.locator(".app-shell")).toHaveClass(/dark/);
});
