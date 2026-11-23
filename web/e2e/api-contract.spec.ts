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

test("mock resolves share class targets and computes peer-only summary after removal", async ({
  request,
}) => {
  const response = await request.get("/api/comps?target=US%3ANOMA.B&k=3");
  expect(response.ok()).toBeTruthy();
  const initial = await response.json();
  expect(initial.peers).toHaveLength(3);
  expect(initial.target.entity.key).toBe("US:NOMA");
  expect(initial.target.entity.share_class_keys).toEqual(["US:NOMA", "US:NOMA.B"]);
  expect(initial.target.metrics.market_cap_m.display).toBe("4,000.0");
  expect(initial.skipped).toEqual([]);
  expect(initial).toMatchObject({ currency: "USD", requested_k: 3, returned_k: 3, note: null });
  expect(initial).not.toHaveProperty("method");
  expect(initial.peers[0].evidence).not.toHaveProperty("shared_terms");
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

test("mock class keys return the issuer and identify the matched listing", async ({
  request,
}) => {
  const search = await (await request.get("/api/companies?q=Noma+Cloud+Systems+Class+B")).json();
  expect(search.total).toBe(1);
  expect(search.items[0]).toMatchObject({
    key: "US:NOMA",
    matched_key: "US:NOMA.B",
    match: "name_exact",
  });

  const detail = await (await request.get("/api/companies/us%3Anoma.b")).json();
  expect(detail.key).toBe("US:NOMA");
  expect(detail.share_classes).toMatchObject([
    { key: "US:NOMA", counted: true },
    { key: "US:NOMA.B", counted: false },
  ]);
  expect(detail.observations).toHaveLength(2);
  expect(detail.record_ids).toContain("synthetic-014");

  const comps = await (await request.get("/api/comps?target=GB%3ANOMA&exclude=US%3ANOMA.B")).json();
  expect(comps.skipped).toMatchObject([
    { reason: "user_excluded", entity: { key: "US:NOMA" } },
  ]);
});

test("mock peers endpoint returns the comps selection without metrics", async ({
  request,
}) => {
  const query = "target=US%3ANOMA&k=50";
  const peers = await (await request.get(`/api/peers?${query}`)).json();
  const comps = await (await request.get(`/api/comps?${query}`)).json();
  expect(peers.peers.map((p: { entity: { key: string } }) => p.entity.key)).toEqual(
    comps.peers.map((p: { entity: { key: string } }) => p.entity.key),
  );
  expect(peers.peers[0]).not.toHaveProperty("metrics");
  expect(peers.returned_k).toBeLessThan(50);
  expect(peers.note).toBeTruthy();
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
