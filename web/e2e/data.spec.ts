import { expect, test } from "@playwright/test";

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
