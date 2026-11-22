"use client";

import { titleLabel } from "@/lib/utils";
import { useEffect, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { api } from "@/lib/api";
import type {
  CompaniesResponse,
  DatasetResponse,
  Finding,
  FindingsResponse,
  Severity,
} from "@/lib/api-types";
import { DataTable } from "@/components/data-table";
import { CompanyDetail } from "@/components/company-detail";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const severities: Severity[] = ["error", "limitation", "warning", "info"];
const pageSize = 20;
function useResource<T>(path: string | null) {
  const [result, setResult] = useState<{
    path: string;
    data?: T;
    error?: string;
  } | null>(null);
  useEffect(() => {
    if (path === null) return;
    const controller = new AbortController();
    api<T>(path, { signal: controller.signal }).then(
      (data) => {
        if (!controller.signal.aborted) setResult({ path, data });
      },
      (cause: unknown) => {
        if (!controller.signal.aborted)
          setResult({
            path,
            error:
              cause instanceof Error ? cause.message : "Unable to load data.",
          });
      },
    );
    return () => controller.abort();
  }, [path]);
  const current = result?.path === path ? result : null;
  return {
    data: current?.data,
    error: current?.error,
    loading: path !== null && current === null,
  };
}
function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <Badge variant="outline" className={`severity-${severity}`}>
      {titleLabel(severity)}
    </Badge>
  );
}
function SourceBadge({ source }: { source: Finding["source"] }) {
  return source === "derived" ? (
    <Badge
      variant="outline"
      className="border-violet-400/50 bg-violet-500/10 text-violet-700 dark:text-violet-300"
    >
      Model-Derived
    </Badge>
  ) : (
    <span className="muted">Validation</span>
  );
}
function Pager({
  offset,
  total,
  loading,
  onChange,
}: {
  offset: number;
  total: number;
  loading: boolean;
  onChange: (offset: number) => void;
}) {
  return (
    <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
      <p className="muted text-sm" aria-live="polite">
        {total === 0
          ? "0 results"
          : `${offset + 1}–${Math.min(offset + pageSize, total)} of ${total}`}
      </p>
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={loading || offset === 0}
          onClick={() => onChange(Math.max(0, offset - pageSize))}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={loading || offset + pageSize >= total}
          onClick={() => onChange(offset + pageSize)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
const codeColumns: ColumnDef<DatasetResponse["findings_by_code"][number]>[] = [
  {
    accessorKey: "code",
    header: "Finding Code",
    cell: ({ row }) => (
      <span className="font-mono text-sm">{row.original.code}</span>
    ),
  },
  {
    accessorKey: "severity",
    header: "Severity",
    cell: ({ row }) => <SeverityBadge severity={row.original.severity} />,
  },
  {
    accessorKey: "source",
    header: "Source",
    cell: ({ row }) => <SourceBadge source={row.original.source} />,
  },
  { accessorKey: "count", header: "Count" },
];
const findingColumns: ColumnDef<Finding>[] = [
  {
    accessorKey: "severity",
    header: "Severity",
    cell: ({ row }) => <SeverityBadge severity={row.original.severity} />,
  },
  {
    accessorKey: "code",
    header: "Code",
    cell: ({ row }) => (
      <span className="font-mono text-sm">{row.original.code}</span>
    ),
  },
  {
    accessorKey: "message",
    header: "Finding",
    cell: ({ row }) => (
      <div className="min-w-64 max-w-md whitespace-normal">
        <p>{row.original.message}</p>
        <p className="muted mt-1 text-sm">
          Fields: {row.original.fields.join(", ") || "—"} · Affects:{" "}
          {row.original.affects.join(", ") || "—"}
        </p>
        <p className="muted mt-1 text-sm">
          Records: {row.original.record_ids.join(", ") || "—"}
        </p>
      </div>
    ),
  },
  {
    id: "entities",
    accessorFn: (finding) => finding.entity_keys.join(", "),
    header: "Company",
    cell: ({ row }) => (
      <span className="font-mono text-sm">
        {row.original.entity_keys.join(", ") || "—"}
      </span>
    ),
  },
  {
    accessorKey: "source",
    header: "Source",
    cell: ({ row }) => <SourceBadge source={row.original.source} />,
  },
];

export default function DataPage() {
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null);
  const [companyQuery, setCompanyQuery] = useState("");
  const [companySector, setCompanySector] = useState("");
  const [companySeverity, setCompanySeverity] = useState("");
  const [companyOffset, setCompanyOffset] = useState(0);
  const [findingsOpen, setFindingsOpen] = useState(false);
  const [findingSeverity, setFindingSeverity] = useState("");
  const [findingCode, setFindingCode] = useState("");
  const [findingEntity, setFindingEntity] = useState("");
  const [findingOffset, setFindingOffset] = useState(0);
  const dataset = useResource<DatasetResponse>("/dataset");
  const companyParams = new URLSearchParams({
    limit: String(pageSize),
    offset: String(companyOffset),
  });
  if (companyQuery) companyParams.set("q", companyQuery);
  if (companySector) companyParams.set("sector", companySector);
  if (companySeverity) companyParams.set("has_findings", companySeverity);
  const companies = useResource<CompaniesResponse>(`/companies?${companyParams}`);
  const findingParams = new URLSearchParams({
    limit: String(pageSize),
    offset: String(findingOffset),
  });
  if (findingSeverity) findingParams.set("severity", findingSeverity);
  if (findingCode) findingParams.set("code", findingCode);
  if (findingEntity) findingParams.set("entity", findingEntity);
  const findings = useResource<FindingsResponse>(
    findingsOpen ? `/dataset/findings?${findingParams}` : null,
  );
  const companyColumns: ColumnDef<CompaniesResponse["items"][number]>[] = [
    {
      accessorKey: "name",
      header: "Company",
      cell: ({ row }) => (
        <button
          type="button"
          className="text-left font-medium hover:underline focus-visible:outline-2 focus-visible:outline-offset-4"
          onClick={(event) => {
            event.stopPropagation();
            setSelectedCompany(row.original.matched_key ?? row.original.key);
          }}
        >
          {row.original.name}
          <span className="muted mt-1 block font-mono text-sm">
            {row.original.key}
          </span>
          {row.original.matched_key && (
            <span className="muted block text-sm">
              Matched Share Class <code>{row.original.matched_key}</code>
            </span>
          )}
        </button>
      ),
    },
    { accessorKey: "country", header: "Country" },
    { accessorKey: "sector", header: "Sector" },
    { accessorKey: "industry", header: "Industry" },
    { accessorKey: "latest_price_date", header: "Latest Price Date" },
    {
      id: "findings",
      header: "Findings",
      enableSorting: false,
      cell: ({ row }) => (
        <div className="flex flex-wrap gap-1">
          {severities.map(
            (severity) =>
              row.original.finding_counts[severity] > 0 && (
                <Badge
                  key={severity}
                  variant="outline"
                  className={`severity-${severity}`}
                >
                  {row.original.finding_counts[severity]} {titleLabel(severity)}
                </Badge>
              ),
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <header>
        <h1>Data & Integrity</h1>
        <p className="muted mt-2">Search companies and open their details.</p>
      </header>

      <section className="panel space-y-5" aria-labelledby="companies-heading">
        <div>
          <h2 id="companies-heading" className="section-heading">
            Companies
          </h2>
          <p className="muted mt-1">
            Select a company to inspect its observations, findings and
            calculation trace.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="field" htmlFor="company-search">
            <span>Search Companies</span>
            <Input
              id="company-search"
              placeholder="Company Name, Ticker or Key"
              value={companyQuery}
              onChange={(event) => {
                setCompanyQuery(event.target.value);
                setCompanyOffset(0);
              }}
            />
          </label>
          <label className="field" htmlFor="company-sector">
            <span>Company Sector</span>
            <Input
              id="company-sector"
              placeholder="All Sectors"
              value={companySector}
              onChange={(event) => {
                setCompanySector(event.target.value);
                setCompanyOffset(0);
              }}
            />
          </label>
          <label className="field" htmlFor="company-severity">
            <span>Company Finding Severity</span>
            <select
              id="company-severity"
              value={companySeverity}
              onChange={(event) => {
                setCompanySeverity(event.target.value);
                setCompanyOffset(0);
              }}
            >
              <option value="">All Severities</option>
              {severities.map((severity) => (
                <option key={severity} value={severity}>
                  {titleLabel(severity)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {companies.loading && (
          <p className="muted" role="status">
            Loading companies…
          </p>
        )}
        {companies.error && (
          <p className="error" role="alert">
            {companies.error}
          </p>
        )}
        {companies.data && (
          <>
            <DataTable
              columns={companyColumns}
              data={companies.data.items}
              onRowClick={(company) =>
                setSelectedCompany(company.matched_key ?? company.key)
              }
            />
            <Pager
              offset={companyOffset}
              total={companies.data.total}
              loading={companies.loading}
              onChange={setCompanyOffset}
            />
            <p className="muted text-sm">
              Dataset Version: {companies.data.dataset_version}
            </p>
          </>
        )}
      </section>

      <section className="space-y-5" aria-labelledby="dataset-health-heading">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="dataset-health-heading" className="section-heading">
            Dataset Health
          </h2>
          {dataset.data && (
            <Badge variant="outline">
              Version {dataset.data.dataset_version}
            </Badge>
          )}
        </div>
        {dataset.loading && (
          <p className="muted" role="status">
            Loading dataset health…
          </p>
        )}
        {dataset.error && (
          <p className="error" role="alert">
            {dataset.error}
          </p>
        )}
        {dataset.data && (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              {(
                [
                  ["Entities", dataset.data.counts.entities],
                  ["Records", dataset.data.counts.records],
                ] as const
              ).map(([label, count]) => (
                <div className="panel" key={label}>
                  <p className="muted text-sm">{label}</p>
                  <p className="mt-2 text-3xl font-semibold tabular-nums">
                    {count}
                  </p>
                </div>
              ))}
            </div>
            <details className="rounded-lg border p-4">
              <summary className="cursor-pointer font-medium">
                Source Files & Hashes
              </summary>
              <p className="muted mt-3 text-sm">
                Reference Date: {dataset.data.reference_date || "—"}
              </p>
              <p className="muted mt-3 break-all text-sm">
                {dataset.data.source.data_dir}
              </p>
              <dl className="mt-3 space-y-3">
                {dataset.data.source.files.map((file) => (
                  <div key={file.name}>
                    <dt className="font-medium">{file.name}</dt>
                    <dd className="muted mt-1 break-all font-mono text-sm">
                      SHA-256: {file.sha256}
                    </dd>
                  </div>
                ))}
              </dl>
            </details>
          </>
        )}
      </section>

      <details
        className="rounded-lg border px-4 py-3"
        onToggle={(event) => setFindingsOpen(event.currentTarget.open)}
      >
        <summary className="cursor-pointer font-medium">Dataset Findings</summary>
        <div className="mt-4 space-y-5">
          {dataset.data && (
            <section className="space-y-3" aria-labelledby="findings-by-code-heading">
              <h3 id="findings-by-code-heading" className="font-semibold">Findings by Code</h3>
              <ul className="flex flex-wrap gap-x-4 gap-y-2">
                {severities.map((severity) => (
                  <li key={severity} className="flex items-center gap-2 text-sm">
                    <SeverityBadge severity={severity} />
                    <span className="tabular-nums">
                      {dataset.data!.findings_by_severity[severity]}
                    </span>
                  </li>
                ))}
              </ul>
              <DataTable
                columns={codeColumns}
                data={dataset.data.findings_by_code}
              />
            </section>
          )}
          <section className="space-y-5" aria-labelledby="findings-heading">
            <div>
              <h3 id="findings-heading" className="font-semibold">Findings</h3>
              <p className="muted mt-1">
                Model-derived findings flag possible issues for review.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <label className="field" htmlFor="finding-severity">
                <span>Finding Severity</span>
                <select
                  id="finding-severity"
                  value={findingSeverity}
                  onChange={(event) => {
                    setFindingSeverity(event.target.value);
                    setFindingOffset(0);
                  }}
                >
                  <option value="">All Severities</option>
                  {severities.map((severity) => (
                    <option key={severity} value={severity}>
                      {titleLabel(severity)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field" htmlFor="finding-code">
                <span>Finding Code</span>
                <Input
                  id="finding-code"
                  placeholder="e.g. missing_value"
                  value={findingCode}
                  onChange={(event) => {
                    setFindingCode(event.target.value);
                    setFindingOffset(0);
                  }}
                />
              </label>
              <label className="field" htmlFor="finding-company">
                <span>Finding Company Key</span>
                <Input
                  id="finding-company"
                  placeholder="e.g. US:NOMA"
                  value={findingEntity}
                  onChange={(event) => {
                    setFindingEntity(event.target.value);
                    setFindingOffset(0);
                  }}
                />
              </label>
            </div>
            {findings.loading && (
              <p className="muted" role="status">
                Loading findings…
              </p>
            )}
            {findings.error && (
              <p className="error" role="alert">
                {findings.error}
              </p>
            )}
            {findings.data && (
              <>
                <DataTable columns={findingColumns} data={findings.data.items} />
                <Pager
                  offset={findingOffset}
                  total={findings.data.total}
                  loading={findings.loading}
                  onChange={setFindingOffset}
                />
                <p className="muted text-sm">
                  Dataset Version: {findings.data.dataset_version}
                </p>
              </>
            )}
          </section>
        </div>
      </details>
      <CompanyDetail
        companyKey={selectedCompany}
        onClose={() => setSelectedCompany(null)}
      />
    </div>
  );
}
