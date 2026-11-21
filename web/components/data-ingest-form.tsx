"use client";

import { sentenceLabel } from "@/lib/utils";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import type { Finding, IngestResult, RawRecord } from "@/lib/api-types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { MetricsView } from "@/components/metrics-view";
import { Findings } from "@/components/findings";

const textFields = [
  ["id", "Record ID", "text"],
  ["ticker", "Ticker", "text"],
  ["name", "Company name", "text"],
  ["country", "Country (optional)", "text"],
  ["sector", "Sector", "text"],
  ["industry", "Industry", "text"],
  ["sub_industry", "Sub-industry", "text"],
  ["price_currency", "Price currency", "text"],
  ["reporting_currency", "Reporting currency", "text"],
  ["fiscal_year_end", "Fiscal year end (MM-DD)", "text"],
  ["price_date", "Price date", "date"],
] as const;
const numericFields = [
  ["price", "Share price (price currency)"],
  ["shares_outstanding", "Shares outstanding (millions)"],
  ["total_debt", "Total debt"],
  ["cash", "Cash"],
  ["revenue", "Revenue (LTM)"],
  ["ebitda", "EBITDA (LTM)"],
  ["net_income", "Net income (LTM)"],
] as const;
type FormValues = Record<keyof RawRecord, string>;
const emptyValues = Object.fromEntries(
  [...textFields, ...numericFields, ["description"], ["units"]].map(([key]) => [
    key,
    "",
  ]),
) as FormValues;

export function DataIngestForm({ onSaved }: { onSaved: () => void }) {
  const [values, setValues] = useState<FormValues>(emptyValues);
  const [preview, setPreview] = useState<IngestResult | null>(null);
  const [previewedRecord, setPreviewedRecord] = useState<RawRecord | null>(
    null,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [errorFindings, setErrorFindings] = useState<Finding[]>([]);
  const [saved, setSaved] = useState("");

  function update(key: keyof RawRecord, value: string) {
    setValues((previous) => ({ ...previous, [key]: value }));
    setPreview(null);
    setPreviewedRecord(null);
    setSaved("");
    setError("");
    setErrorFindings([]);
  }
  function reportError(cause: unknown) {
    setError(
      cause instanceof Error
        ? cause.message
        : "The request could not be completed.",
    );
    if (cause instanceof ApiError && Array.isArray(cause.details.findings))
      setErrorFindings(cause.details.findings as Finding[]);
  }
  async function handlePreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSaved("");
    setErrorFindings([]);
    setPreview(null);
    setPreviewedRecord(null);
    const numberOrNull = (key: (typeof numericFields)[number][0]) =>
      values[key].trim() === "" ? null : Number(values[key]);
    const record: RawRecord = {
      ...values,
      units: values.units as RawRecord["units"],
      price: numberOrNull("price"),
      shares_outstanding: numberOrNull("shares_outstanding"),
      total_debt: numberOrNull("total_debt"),
      cash: numberOrNull("cash"),
      revenue: numberOrNull("revenue"),
      ebitda: numberOrNull("ebitda"),
      net_income: numberOrNull("net_income"),
    };
    try {
      const result = await api<IngestResult>("/ingest/preview", {
        method: "POST",
        body: JSON.stringify(record),
      });
      setPreview(result);
      setPreviewedRecord(record);
    } catch (cause) {
      reportError(cause);
    } finally {
      setBusy(false);
    }
  }
  async function save() {
    if (!preview?.accepted || !previewedRecord) return;
    setBusy(true);
    setError("");
    setErrorFindings([]);
    try {
      const result = await api<IngestResult & { dataset_version: string }>(
        "/ingest/records",
        { method: "POST", body: JSON.stringify(previewedRecord) },
      );
      setPreview(result);
      setPreviewedRecord(null);
      setSaved(
        `Saved ${result.resolution.key ?? "record"}. Dataset version: ${result.dataset_version}.`,
      );
      onSaved();
    } catch (cause) {
      reportError(cause);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel space-y-6" aria-labelledby="add-company-heading">
      <div>
        <p className="eyebrow">Manual addition</p>
        <h2 id="add-company-heading" className="section-heading">
          Add company
        </h2>
        <p className="muted mt-2">
          Additions are held in memory only and are lost on restart. Input files
          are never changed.
        </p>
      </div>
      <form onSubmit={handlePreview} className="space-y-6">
        <fieldset disabled={busy} className="space-y-5">
          <legend className="sr-only">Company record</legend>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {textFields.map(([key, label, type]) => (
              <label className="field" key={key} htmlFor={`record-${key}`}>
                <span>{label}</span>
                <Input
                  id={`record-${key}`}
                  name={key}
                  type={type}
                  value={values[key]}
                  onChange={(event) => update(key, event.target.value)}
                  required={key !== "country"}
                />
              </label>
            ))}
            <label className="field" htmlFor="record-units">
              <span>Reporting units</span>
              <select
                id="record-units"
                name="units"
                value={values.units}
                onChange={(event) => update("units", event.target.value)}
                required
              >
                <option value="">Choose units</option>
                <option value="millions">Millions</option>
                <option value="thousands">Thousands</option>
              </select>
            </label>
          </div>
          <label className="field" htmlFor="record-description">
            <span>Business description</span>
            <textarea
              id="record-description"
              name="description"
              rows={3}
              value={values.description}
              onChange={(event) => update("description", event.target.value)}
              required
            />
          </label>
          <p className="muted">
            Leave unavailable numeric values blank; they are sent as null. Debt,
            cash and LTM financials use the reporting currency and units above.
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {numericFields.map(([key, label]) => (
              <label className="field" key={key} htmlFor={`record-${key}`}>
                <span>{label}</span>
                <Input
                  id={`record-${key}`}
                  name={key}
                  type="number"
                  step="any"
                  value={values[key]}
                  onChange={(event) => update(key, event.target.value)}
                />
              </label>
            ))}
          </div>
          <Button type="submit" disabled={busy}>
            {busy ? "Processing…" : "Preview addition"}
          </Button>
        </fieldset>
      </form>
      {error && (
        <div role="alert" className="error">
          <p>{error}</p>
          {errorFindings.length > 0 && <Findings findings={errorFindings} />}
        </div>
      )}
      {saved && (
        <p
          role="status"
          className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4"
        >
          {saved}
        </p>
      )}
      {preview && (
        <div className="space-y-5 border-t pt-6" aria-label="Addition preview">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="font-semibold">
              {saved ? "Saved result" : "Preview result"}
            </h3>
            <Badge variant="outline">
              {sentenceLabel(preview.resolution.action)}
            </Badge>
            <span className="font-mono text-sm">{preview.resolution.key}</span>
          </div>
          {!preview.accepted && (
            <p className="error">
              This record was rejected. Review the findings before saving.
            </p>
          )}
          {preview.entity && (
            <>
              <div>
                <h4 className="mb-3 font-semibold">Normalized USD values</h4>
                <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {Object.entries(preview.entity.latest.usd).map(
                    ([key, value]) => (
                      <div key={key} className="rounded-lg border p-3">
                        <dt className="muted text-sm">
                          {sentenceLabel(key)}
                          {key === "price"
                            ? " · USD per share"
                            : " · USD millions"}
                        </dt>
                        <dd className="mt-1 font-mono">{value ?? "—"}</dd>
                      </div>
                    ),
                  )}
                </dl>
              </div>
              <MetricsView metrics={preview.entity.metrics} />
            </>
          )}
          <Findings findings={preview.findings} />
          {!saved && (
            <Button
              type="button"
              onClick={save}
              disabled={busy || !preview.accepted || !previewedRecord}
            >
              {busy ? "Saving…" : "Save to memory"}
            </Button>
          )}
        </div>
      )}
    </section>
  );
}
