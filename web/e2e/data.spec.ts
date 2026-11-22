import { expect, test } from "@playwright/test";

test("manual record requires preview and persists only after Save", async ({
  page,
  request,
}) => {
  const key = `*:QA${Date.now()}`;
  const ticker = key.split(":")[1];
  await page.goto("/data");
  await expect(page.getByRole("heading", { name: "Data & Integrity", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Dataset Health", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Add Company", exact: true }).click();
  const inputs: Record<string, string> = {
    "Record ID": `qa-${ticker}`,
    Ticker: ticker,
    "Company Name": "QA Synthetic Software",
    Sector: "Information Technology",
    Industry: "Software",
    "Sub-Industry": "Application Software",
    "Price Currency": "USD",
    "Reporting Currency": "USD",
    "Fiscal Year End (MM-DD)": "12-31",
    "Price Date": "2026-11-20",
    "Business Description":
      "Synthetic cloud software for enterprise workflows.",
    "Share Price (Price Currency)": "10",
    "Shares Outstanding (Millions)": "20",
    "Total Debt": "30",
    Cash: "10",
    "Revenue (LTM)": "100",
    "EBITDA (LTM)": "20",
  };
  for (const [label, value] of Object.entries(inputs))
    await page.getByLabel(label, { exact: true }).fill(value);
  await page
    .getByRole("combobox", { name: "Reporting Units", exact: true })
    .selectOption("millions");
  await expect(
    page.getByRole("button", { name: "Save to Memory" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Preview Addition" }).click();
  await expect(
    page.getByRole("heading", { name: "Preview Result" }),
  ).toBeVisible();
  await expect(page.getByText("Create", { exact: true })).toBeVisible();
  expect(
    (await request.get(`/api/companies/${encodeURIComponent(key)}`)).status(),
  ).toBe(404);
  await page.getByRole("button", { name: "Save to Memory" }).click();
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
  await page.getByLabel("Finding Company Key", { exact: true }).fill("US:ORBT");
  await expect(
    findings.getByText("Model-Derived", { exact: true }),
  ).toBeVisible();
  await expect(findings.getByText("US:ORBT", { exact: true })).toBeVisible();
  await page.getByLabel("Search Companies", { exact: true }).fill("US:NOMA");
  await page
    .getByRole("button", { name: /Noma Cloud Systems.*US:NOMA$/ })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Aliases" })).toBeVisible();
  await expect(
    dialog.getByText("Noma Software, Noma Cloud Systems", { exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("heading", { name: "Observation History" }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Close Panel" }).click();
  await page.getByRole("button", { name: "Switch to Dark Mode" }).click();
  await expect(page.locator(".app-shell")).toHaveClass(/dark/);
});
