import { expect, test } from "@playwright/test";

test("Compare keeps identities distinct, exposes evidence and trace, and refetches removals", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Number of Peers")).toHaveValue("10");
  await page.getByLabel("Target Company").fill("NOMA");
  await expect(
    page.getByRole("button", { name: /Noma Analytics.*GB:NOMA/ }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /Noma Cloud Systems.*US:NOMA$/ })
    .click();
  await expect(
    page.getByRole("heading", { name: /Noma Cloud Systems US:NOMA/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Valuation Summary" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Evidence", exact: true })
    .first()
    .click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: "Peer Evidence" }),
  ).toBeVisible();
  await expect(
    dialog.getByText("A similarity score, not a probability."),
  ).toBeVisible();
  await expect(
    dialog.getByRole("heading", { name: "Shared Terms" }),
  ).toHaveCount(0);
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", { name: "Calculation Trace", exact: true })
    .click();
  await expect(
    dialog.getByRole("heading", { name: "Unrounded Metric Values" }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("heading", { name: "Observation History" }),
  ).toBeVisible();
  await expect(
    dialog.getByText("Noma Software, Noma Cloud Systems, Noma Cloud Systems Class B", {
      exact: true,
    }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByLabel("Target Company").fill("US:NOMA.B");
  await page
    .getByRole("button", { name: /Noma Cloud Systems.*Matched Share Class US:NOMA.B.*US:NOMA$/ })
    .click();
  await expect(
    page.getByRole("heading", { name: "Valuation Summary" }),
  ).toBeVisible();
  const removal = page.waitForResponse(
    (response) =>
      response.url().includes("/api/comps?") &&
      response.url().includes("exclude=GB%3ANOMA"),
  );
  await page
    .getByRole("button", { name: "Remove Noma Analytics", exact: true })
    .click();
  expect((await removal).ok()).toBeTruthy();
  await expect(
    page.getByRole("button", { name: "Remove Noma Analytics", exact: true }),
  ).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Export CSV" })).toHaveAttribute(
    "href",
    /exclude=GB%3ANOMA/,
  );
  await expect(page.getByText("Removed by Analyst")).toBeVisible();
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Remove Noma Analytics", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Number of Peers").fill("3");
  await expect(
    page.getByRole("button", { name: "Evidence", exact: true }),
  ).toHaveCount(3);
});

test("Compare surfaces API errors without replacing them with mock data", async ({
  page,
}) => {
  await page.route("**/api/companies?**", (route) =>
    route.fulfill({
      status: 422,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "invalid_request",
          message: "Synthetic request failure",
          details: {},
        },
      }),
    }),
  );
  await page.goto("/");
  await page.getByLabel("Target Company").fill("NOMA");
  await expect(
    page.getByRole("alert").filter({ hasText: "Synthetic request failure" }),
  ).toHaveText("Synthetic request failure");
});
