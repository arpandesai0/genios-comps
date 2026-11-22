import { expect, test } from "@playwright/test";

test("Data filters findings and companies and opens observation provenance", async ({
  page,
}) => {
  const findingsRequests: URL[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname === "/api/dataset/findings") findingsRequests.push(url);
  });
  await page.goto("/data");
  await expect(page.getByRole("main").getByRole("heading", { level: 2 })).toHaveText([
    "Companies",
    "Dataset Health",
  ]);
  const findingsSummary = page.getByText("Dataset Findings", { exact: true });
  const findingsByCode = page.getByText("Findings by Code", { exact: true });
  await expect(findingsSummary).toBeVisible();
  await expect(findingsByCode).toBeHidden();
  await page.getByLabel("Search Companies", { exact: true }).fill("NOMA.B");
  const match = page.getByRole("button", {
    name: /Noma Cloud Systems.*US:NOMA.*Matched Share Class US:NOMA.B/,
  });
  await expect(match).toHaveCount(1);
  await match.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Noma Cloud Systems", exact: true })).toBeVisible();
  const shareClasses = dialog.getByRole("region", { name: "Share Classes" });
  await expect(shareClasses.getByRole("listitem")).toHaveCount(2);
  await expect(shareClasses.getByRole("listitem").first()).toContainText("Counted Toward Market Cap");
  await expect(shareClasses.getByRole("listitem").last()).toContainText("Duplicate Listing · Shares Counted Once");
  await expect(dialog.getByRole("heading", { name: "Aliases" })).toBeVisible();
  await expect(
    dialog.getByText("Noma Software, Noma Cloud Systems, Noma Cloud Systems Class B", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("heading", { name: "Observation History" }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Close Panel" }).click();
  expect(findingsRequests).toHaveLength(0);
  await findingsSummary.click();
  await expect(findingsByCode).toBeVisible();
  await expect.poll(() => findingsRequests.length).toBeGreaterThan(0);
  const findings = page.getByRole("region", { name: "Findings", exact: true });
  await page.getByLabel("Finding Company Key", { exact: true }).fill("US:ORBT");
  await expect.poll(() =>
    findingsRequests.some((url) => url.searchParams.get("entity") === "US:ORBT"),
  ).toBe(true);
  await expect(
    findings.getByText("Model-Derived", { exact: true }),
  ).toBeVisible();
  await expect(findings.getByText("US:ORBT", { exact: true })).toBeVisible();
  await findingsSummary.click();
  await expect(findingsByCode).toBeHidden();
  await page.getByRole("button", { name: "Switch to Dark Mode" }).click();
  await expect(page.locator(".app-shell")).toHaveClass(/dark/);
});
