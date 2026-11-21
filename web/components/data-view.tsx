"use client";

import { useEffect, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { api } from "@/lib/api";
import type {
  CompaniesResponse,
  DatasetResponse,
  EntitySummary,
  Finding,
  FindingsResponse,
  Severity,
} from "@/lib/api-types";
import { DataTable } from "@/components/data-table";
import { CompanyDetail } from "@/components/company-detail";
import { DataIngestForm } from "@/components/data-ingest-form";
import { features } from "@/lib/features";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const severities: Severity[] = ["error", "limitation", "warning", "info"];
const pageSize = 20;
function useResource<T>(path: string, revision: number) {
  const [result, setResult] = useState<{
    path: string;
    revision: number;
    data?: T;
    error?: string;
  } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    api<T>(path, { signal: controller.signal }).then(
      (data) => {
        if (!controller.signal.aborted) setResult({ path, revision, data });
      },
      (cause: unknown) => {
        if (!controller.signal.aborted)
          setResult({
            path,
            revision,
            error:
              cause instanceof Error ? cause.message : "Unable to load data.",
          });
      },
    );
    return () => controller.abort();
  }, [path, revision]);
  const current =
    result?.path === path && result.revision === revision ? result : null;
  return {
    data: current?.data,
    error: current?.error,
    loading: current === null,
  };
}
function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <Badge variant="outline" className={`severity-${severity}`}>
      {severity}
    </Badge>
  );
}
function SourceBadge({ source }: { source: Finding["source"] }) {
  return source === "derived" ? (
    <Badge
      variant="outline"
      className="border-violet-400/50 bg-violet-500/10 text-violet-700 dark:text-violet-300"
    >
      model-derived
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
    header: "Finding code",
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
  const [revision, setRevision] = useState(0);
  const [showAdd, setShowAdd] = useState(false);
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null);
  const [companyQuery, setCompanyQuery] = useState("");
  const [companySector, setCompanySector] = useState("");
  const [companySeverity, setCompanySeverity] = useState("");
  const [companyOffset, setCompanyOffset] = useState(0);
  const [findingSeverity, setFindingSeverity] = useState("");
  const [findingCode, setFindingCode] = useState("");
  const [findingEntity, setFindingEntity] = useState("");
  const [findingOffset, setFindingOffset] = useState(0);
  const dataset = useResource<DatasetResponse>("/dataset", revision);
  const companyParams = new URLSearchParams({
    limit: String(pageSize),
    offset: String(companyOffset),
  });
  if (companyQuery) companyParams.set("q", companyQuery);
  if (companySector) companyParams.set("sector", companySector);
  if (companySeverity) companyParams.set("has_findings", companySeverity);
  const companies = useResource<CompaniesResponse>(
    `/companies?${companyParams}`,
    revision,
  );
  const findingParams = new URLSearchParams({
    limit: String(pageSize),
    offset: String(findingOffset),
  });
  if (findingSeverity) findingParams.set("severity", findingSeverity);
  if (findingCode) findingParams.set("code", findingCode);
  if (findingEntity) findingParams.set("entity", findingEntity);
  const findings = useResource<FindingsResponse>(
    `/dataset/findings?${findingParams}`,
    revision,
  );
  const companyColumns: ColumnDef<EntitySummary>[] = [
    {
      accessorKey: "name",
      header: "Company",
      cell: ({ row }) => (
        <button
          type="button"
          className="text-left font-medium hover:underline focus-visible:outline-2 focus-visible:outline-offset-4"
          onClick={(event) => {
            event.stopPropagation();
            setSelectedCompany(row.original.key);
          }}
        >
          {row.original.name}
          <span className="muted mt-1 block font-mono text-sm">
            {row.original.key}
          </span>
        </button>
      ),
    },
    { accessorKey: "country", header: "Country" },
    { accessorKey: "sector", header: "Sector" },
    { accessorKey: "industry", header: "Industry" },
    { accessorKey: "latest_price_date", header: "Latest price date" },
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
                  {row.original.finding_counts[severity]} {severity}
                </Badge>
              ),
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1>Data & integrity</h1>
          <p className="muted mt-2">
            Inspect the source, review findings and preview manual additions.
          </p>
        </div>
        {features.manualIngest && (
          <Button
            onClick={() => setShowAdd(!showAdd)}
            aria-expanded={showAdd}
            aria-controls="add-company-section"
          >
            {showAdd ? "Close addition form" : "Add company"}
          </Button>
        )}
      </header>
      {features.manualIngest && showAdd && (
        <div id="add-company-section">
          <DataIngestForm
            onSaved={() => {
              setRevision((value) => value + 1);
              setCompanyOffset(0);
              setFindingOffset(0);
            }}
          />
        </div>
      )}

      <section className="space-y-5" aria-labelledby="dataset-health-heading">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="dataset-health-heading" className="section-heading">
            Dataset health
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
            <div className="grid gap-4 sm:grid-cols-3">
              {(
                [
                  ["Entities", dataset.data.counts.entities],
                  ["Records", dataset.data.counts.records],
                  ["Manual additions", dataset.data.counts.manual_additions],
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
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {severities.map((severity) => (
                <div
                  className="panel flex items-center justify-between gap-4"
                  key={severity}
                >
                  <SeverityBadge severity={severity} />
                  <span className="text-2xl font-semibold tabular-nums">
                    {dataset.data!.findings_by_severity[severity]}
                  </span>
                </div>
              ))}
            </div>
            <div className="panel space-y-4">
              <div className="flex flex-wrap justify-between gap-2">
                <h3 className="font-semibold">Findings by code</h3>
                <p className="muted text-sm">
                  Reference date: {dataset.data.reference_date}
                </p>
              </div>
              <DataTable
                columns={codeColumns}
                data={dataset.data.findings_by_code}
              />
              <details className="rounded-lg border p-4">
                <summary className="cursor-pointer font-medium">
                  Source files & hashes
                </summary>
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
            </div>
          </>
        )}
      </section>

      <section className="panel space-y-5" aria-labelledby="findings-heading">
        <div>
          <h2 id="findings-heading" className="section-heading">
            Findings
          </h2>
          <p className="muted mt-1">
            Model-derived findings are signals, not facts. Classifications
            remain unchanged.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="field" htmlFor="finding-severity">
            <span>Finding severity</span>
            <select
              id="finding-severity"
              value={findingSeverity}
              onChange={(event) => {
                setFindingSeverity(event.target.value);
                setFindingOffset(0);
              }}
            >
              <option value="">All severities</option>
              {severities.map((severity) => (
                <option key={severity} value={severity}>
                  {severity}
                </option>
              ))}
            </select>
          </label>
          <label className="field" htmlFor="finding-code">
            <span>Finding code</span>
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
            <span>Finding company key</span>
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
              Dataset version: {findings.data.dataset_version}
            </p>
          </>
        )}
      </section>

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
            <span>Search companies</span>
            <Input
              id="company-search"
              placeholder="Company name, ticker or key"
              value={companyQuery}
              onChange={(event) => {
                setCompanyQuery(event.target.value);
                setCompanyOffset(0);
              }}
            />
          </label>
          <label className="field" htmlFor="company-sector">
            <span>Company sector</span>
            <Input
              id="company-sector"
              placeholder="All sectors"
              value={companySector}
              onChange={(event) => {
                setCompanySector(event.target.value);
                setCompanyOffset(0);
              }}
            />
          </label>
          <label className="field" htmlFor="company-severity">
            <span>Company finding severity</span>
            <select
              id="company-severity"
              value={companySeverity}
              onChange={(event) => {
                setCompanySeverity(event.target.value);
                setCompanyOffset(0);
              }}
            >
              <option value="">All severities</option>
              {severities.map((severity) => (
                <option key={severity} value={severity}>
                  {severity}
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
              onRowClick={(company) => setSelectedCompany(company.key)}
            />
            <Pager
              offset={companyOffset}
              total={companies.data.total}
              loading={companies.loading}
              onChange={setCompanyOffset}
            />
            <p className="muted text-sm">
              Dataset version: {companies.data.dataset_version}
            </p>
          </>
        )}
      </section>
      <CompanyDetail
        companyKey={selectedCompany}
        onClose={() => setSelectedCompany(null)}
      />
    </div>
  );
}
