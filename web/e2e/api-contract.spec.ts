import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

test("mock search preserves ambiguous keys and rejects invalid peer counts", async ({
  request,
}) => {
  const search = await (await request.get("/api/companies?q=NOMA")).json();
  const keys = search.items.map((item: { key: string }) => item.key);
  expect(keys).toContain("US:NOMA");
  expect(keys).toContain("GB:NOMA");
  const invalid = await request.get("/api/comps?target=US%3ANOMA&k=0");
  expect(invalid.status()).toBe(422);
  expect((await invalid.json()).error.code).toBe("invalid_request");
});

test("mock excludes siblings and computes peer-only summary after removal", async ({
  request,
}) => {
  const response = await request.get("/api/comps?target=US%3ANOMA&k=3");
  expect(response.ok()).toBeTruthy();
  const initial = await response.json();
  expect(initial.peers).toHaveLength(3);
  expect(initial.excluded).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        reason: "possible_same_issuer",
        entity: expect.objectContaining({ key: "US:NOMA.B" }),
      }),
    ]),
  );
  const removed = initial.peers[0].entity.key;
  const query = new URLSearchParams({
    target: "US:NOMA",
    k: "3",
    exclude: removed,
  });
  const updated = await (await request.get(`/api/comps?${query}`)).json();
  expect(updated.peers).toHaveLength(3);
  expect(
    updated.peers.some(
      (peer: { entity: { key: string } }) => peer.entity.key === removed,
    ),
  ).toBeFalsy();
  expect(updated.summary.ev_revenue.n).toBe(3);
  const csv = await request.get(`/api/comps.csv?${query}`);
  expect(csv.headers()["content-type"]).toContain("text/csv");
  const text = await csv.text();
  expect(text).toContain("US:NOMA");
  expect(text).not.toContain(removed);
  expect(text).toContain(updated.summary.ev_revenue.display.mean);
});

test("dataset hashes match fixture files", async ({
  request,
}) => {
  const dataset = await (await request.get("/api/dataset")).json();
  for (const file of dataset.source.files) {
    const bytes = readFileSync(`mocks/${file.name}`);
    expect(file.sha256).toBe(createHash("sha256").update(bytes).digest("hex"));
  }
});
