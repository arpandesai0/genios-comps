"use client";
import { titleLabel } from "@/lib/utils";
import { useEffect, useState } from "react";
import {
  Download,
  Search,
  SlidersHorizontal,
  X,
  RotateCcw,
  FileSearch,
} from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";
import { api } from "@/lib/api";
import type {
  CompaniesResponse,
  CompsResponse,
  Metrics,
  SkipReason,
} from "@/lib/api-types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { DataTable } from "@/components/data-table";
import { Metric, MetricsView, metricLabels } from "@/components/metrics-view";
import { CompanyDetail } from "@/components/company-detail";
import { Findings } from "@/components/findings";
const DEFAULT_K = 10;
type Peer = CompsResponse["peers"][number];
const skipLabels: Record<SkipReason, string> = {
  near_duplicate_of_target: "Near-Duplicate of Target",
  near_duplicate_of_peer: "Near-Duplicate of a Peer",
  user_excluded: "Removed by Analyst",
  no_description: "No Description",
};
export default function ComparePage() {
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<CompaniesResponse | null>(null);
  const [searchError, setSearchError] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchOffset, setSearchOffset] = useState(0);
  const [target, setTarget] = useState("");
  const [k, setK] = useState(String(DEFAULT_K));
  const [excluded, setExcluded] = useState<string[]>([]);
  const [result, setResult] = useState<CompsResponse | null>(null);
  const [requestError, setError] = useState("");
  const [completed, setCompleted] = useState("");
  const [detail, setDetail] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<Peer | null>(null);
  const validK =
    Number.isInteger(Number(k)) && Number(k) >= 1 && Number(k) <= 50;
  const params = new URLSearchParams({
    target,
    k,
    exclude: excluded.join(","),
  }).toString();
  const loading = !!target && validK && completed !== params;
  const error = completed === params ? requestError : "";
  useEffect(() => {
    if (!query.trim()) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setSearching(true);
      api<CompaniesResponse>(
        `/companies?${new URLSearchParams({ q: query, limit: "20", offset: String(searchOffset) })}`,
        { signal: controller.signal },
      )
        .then((data) => {
          if (controller.signal.aborted) return;
          setMatches(data);
          setSearchError("");
        })
        .catch((e) => {
          if (!controller.signal.aborted) setSearchError(e.message);
        })
        .finally(() => {
          if (!controller.signal.aborted) setSearching(false);
        });
    }, 200);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, searchOffset]);
  useEffect(() => {
    if (!target || !validK) return;
    const controller = new AbortController();
    api<CompsResponse>(`/comps?${params}`, { signal: controller.signal })
      .then((data) => {
        if (controller.signal.aborted) return;
        setResult(data);
        setError("");
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setCompleted(params);
      });
    return () => controller.abort();
  }, [params, target, validK]);
  const columns: ColumnDef<Peer>[] = [
    { accessorKey: "rank", header: "#" },
    {
      id: "company",
      accessorFn: (p) => p.entity.name,
      header: "Company",
      cell: ({ row }) => (
        <button
          className="company-link"
          onClick={() => setDetail(row.original.entity.key)}
        >
          <strong>{row.original.entity.name}</strong>
          <span>{row.original.entity.key}</span>
        </button>
      ),
    },
    {
      id: "similarity",
      accessorFn: (p) => p.evidence.similarity,
      header: "Similarity Score",
      cell: ({ row }) => (
        <span className="score">
          <span className="score-bar">
            <i
              style={{ width: `${row.original.evidence.similarity * 100}%` }}
            />
          </span>
          {row.original.evidence.similarity}
        </span>
      ),
    },
    ...(Object.keys(metricLabels) as (keyof Metrics)[]).map((key) => ({
      id: key,
      accessorFn: (p: Peer) => p.metrics[key].value ?? undefined,
      sortUndefined: "last" as const,
      header:
        key === "enterprise_value_m"
          ? `EV (${result?.currency ?? ""} m)`
          : key === "market_cap_m"
            ? `Market Cap (${result?.currency ?? ""} m)`
            : metricLabels[key],
      cell: ({ row }: { row: { original: Peer } }) => (
        <Metric metric={row.original.metrics[key]} />
      ),
    })),
    {
      id: "findings",
      header: "Findings",
      cell: ({ row }) => (
        <div className="badge-row">
          {row.original.findings.length ? (
            row.original.findings.map((f, i) => (
              <Badge
                key={i}
                className={`severity-${f.severity}`}
                title={f.message}
              >
                {f.source === "derived"
                  ? "Model-Derived"
                  : titleLabel(f.severity)}
              </Badge>
            ))
          ) : (
            <span className="muted">—</span>
          )}
        </div>
      ),
    },
    {
      id: "actions",
      header: "Review",
      cell: ({ row }) => (
        <div className="row-actions">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setEvidence(row.original)}
          >
            Evidence
          </Button>
          <Button
            variant="ghost"
            size="icon"
            disabled={loading}
            aria-label={`Remove ${row.original.entity.name}`}
            onClick={() =>
              setExcluded((prev) => [...prev, row.original.entity.key])
            }
          >
            <X size={15} />
          </Button>
        </div>
      ),
    },
  ];
  const summaryRows = result
    ? (["mean", "median", "high", "low"] as const).map((stat) => ({
        stat,
        ...Object.fromEntries(
          Object.entries(result.summary).map(([key, value]) => [
            key,
            value.display[stat],
          ]),
        ),
      }))
    : [];
  const summaryColumns: ColumnDef<(typeof summaryRows)[number]>[] = [
    {
      accessorKey: "stat",
      header: "Statistic",
      cell: ({ row }) => (
        <span>{titleLabel(row.original.stat)}</span>
      ),
    },
    ...(["ev_revenue", "ev_ebitda", "pe"] as const).map((key) => ({
      id: key,
      header: metricLabels[key],
      cell: ({ row }: { row: { original: (typeof summaryRows)[number] } }) => (
        <span className="metric-number">
          {((row.original as Record<string, unknown>)[key] as string) || "—"}
        </span>
      ),
    })),
  ];
  return (
    <div className="page-stack">
      <h1>Compare Companies</h1>
      <section className="panel search-panel" aria-label="Comparison Controls">
        <div className="search-field">
          <label htmlFor="company-search">Target Company</label>
          <div className="input-icon">
            <Search size={18} />
            <Input
              id="company-search"
              placeholder="Search by company, ticker, or country:ticker"
              value={query}
              autoComplete="off"
              onChange={(e) => {
                setQuery(e.target.value);
                setMatches(null);
                setSearchOffset(0);
                setSearchError("");
              }}
            />
          </div>
        </div>
        <div className="k-field">
          <label htmlFor="peer-count">Number of Peers</label>
          <Input
            id="peer-count"
            type="number"
            min={1}
            max={50}
            step={1}
            value={k}
            onChange={(e) => setK(e.target.value)}
            aria-invalid={!validK}
          />
        </div>
        <div className="search-note">
          <SlidersHorizontal size={16} />
          <span>
            Description Similarity
            <br />
            <small>Size and geography are evidence only</small>
          </span>
        </div>
        {!validK && <p className="error">Enter a whole number from 1 to 50.</p>}
        {query.trim() && (
          <div className="search-results" aria-label="Company Matches">
            {searchError ? (
              <p role="alert" className="error">
                {searchError}
              </p>
            ) : searching || !matches ? (
              <p role="status">Searching…</p>
            ) : (
              <>
                <p className="muted">
                  {matches.total} matches · Select a company by its
                  country:ticker key.
                </p>
                {matches.items.map((c) => (
                  <button
                    key={c.key}
                    className="search-result"
                    onClick={() => {
                      setTarget(c.key);
                      setExcluded([]);
                      if (c.key !== target) setResult(null);
                      setQuery("");
                      setMatches(null);
                    }}
                  >
                    <span>
                      <strong>{c.name}</strong>
                      <small>{c.industry || c.sector || "Unclassified"}</small>
                      {c.matched_key && (
                        <small>Matched Share Class <code>{c.matched_key}</code></small>
                      )}
                    </span>
                    <code>{c.key}</code>
                  </button>
                ))}
                {matches.total > 20 && (
                  <div className="toolbar">
                    <Button
                      variant="outline"
                      disabled={searchOffset === 0}
                      onClick={() => setSearchOffset((n) => n - 20)}
                    >
                      Previous Matches
                    </Button>
                    <Button
                      variant="outline"
                      disabled={searchOffset + 20 >= matches.total}
                      onClick={() => setSearchOffset((n) => n + 20)}
                    >
                      More matches
                    </Button>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </section>
      {loading && (
        <p role="status" className="muted">
          Updating comparison…
        </p>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {!result && !loading && (
        <section className="panel empty-state">
          <FileSearch size={36} />
          <h2>Start with a Company</h2>
          <p className="muted">
            Search above and select a target to explore its peers and valuation
            multiples.
          </p>
        </section>
      )}
      {result && (
        <div
          className={loading || error || !validK ? "results stale" : "results"}
          aria-busy={loading}
        >
          <section className="panel target-card">
            <div className="section-heading">
              <div>
                <p className="eyebrow">TARGET COMPANY</p>
                <h2>
                  {result.target.entity.name}{" "}
                  <span className="entity-key">{result.target.entity.key}</span>
                </h2>
                <p className="muted">
                  {[
                    result.target.entity.sector,
                    result.target.entity.industry,
                    result.target.entity.sub_industry,
                  ]
                    .filter(Boolean)
                    .join(" / ")}
                </p>
              </div>
              <div className="target-actions">
                <span className="muted">
                  Price Date: {result.target.entity.latest_price_date || "—"}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setDetail(result.target.entity.key)}
                >
                  <FileSearch size={15} />
                  Calculation Trace
                </Button>
              </div>
            </div>
            <MetricsView metrics={result.target.metrics} />
            {result.target.findings.length > 0 && (
              <details>
                <summary>
                  {result.target.findings.length} target findings
                </summary>
                <Findings findings={result.target.findings} />
              </details>
            )}
          </section>
          <section className="panel peers-panel">
            <div className="section-heading panel-heading">
              <div>
                <h2>
                  Peer Comparison{" "}
                  <Badge>
                    {result.returned_k === result.requested_k
                      ? result.returned_k
                      : `${result.returned_k} of ${result.requested_k}`}
                  </Badge>
                </h2>
                <p className="muted">
                  Ranked by description similarity · {result.currency} millions
                </p>
              </div>
              <Button variant="outline" size="sm" asChild>
                <a
                  href={`/api/comps.csv?${params}`}
                  download
                  aria-disabled={loading || !!error || !validK}
                  onClick={(e) => {
                    if (loading || error || !validK) e.preventDefault();
                  }}
                >
                  <Download size={15} />
                  Export CSV
                </a>
              </Button>
            </div>
            {result.note && (
              <p role="note" className="note">
                {result.note}
              </p>
            )}
            <DataTable columns={columns} data={result.peers} />
            <div className="table-footnote">
              Similarity is a score, not a probability. The target is excluded
              from peer statistics.
            </div>
          </section>
          <section className="panel summary-panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Peers Only</p>
                <h2>Valuation Summary</h2>
              </div>
              <span className="muted">NM and missing values excluded</span>
            </div>
            <DataTable columns={summaryColumns} data={summaryRows} />
            <div className="summary-counts">
              {Object.entries(result.summary).map(([key, stat]) => (
                <div key={key}>
                  <strong>{metricLabels[key as keyof Metrics]}</strong>
                  <span>
                    n = {stat.n}{" "}
                    <span className="muted">
                      · {stat.n_nm} NM · {stat.n_missing} missing
                    </span>
                  </span>
                </div>
              ))}
            </div>
          </section>
          {(result.skipped.length > 0 || excluded.length > 0) && (
            <section className="panel exclusions">
              <div className="section-heading">
                <div>
                  <h2>Skipped Companies</h2>
                  <p className="muted">
                    Companies passed over while choosing peers, and why. They
                    are not counted in the peer statistics.
                  </p>
                </div>
              </div>
              {result.skipped.map((e) => (
                <div className="exclusion-row" key={e.entity.key}>
                  <div>
                    <strong>{e.entity.name}</strong> <code>{e.entity.key}</code>{" "}
                    <Badge>{skipLabels[e.reason]}</Badge>
                    <p className="muted">
                      {e.detail}
                      {e.similarity !== null &&
                        ` Similarity to the target: ${e.similarity}.`}
                    </p>
                  </div>
                  {e.reason === "user_excluded" && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={loading}
                      onClick={() =>
                        setExcluded((prev) =>
                          prev.filter((key) => key !== e.entity.key),
                        )
                      }
                    >
                      <RotateCcw size={14} />
                      Undo
                    </Button>
                  )}
                </div>
              ))}
              {excluded
                .filter(
                  (key) => !result.skipped.some((e) => e.entity.key === key),
                )
                .map((key) => (
                  <div className="exclusion-row" key={key}>
                    <span>{key} · Removed by analyst</span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={loading}
                      onClick={() =>
                        setExcluded((prev) => prev.filter((k) => k !== key))
                      }
                    >
                      Undo
                    </Button>
                  </div>
                ))}
            </section>
          )}
          <p className="provenance">
            <span>Dataset {result.dataset_version}</span>
          </p>
        </div>
      )}
      <Sheet
        open={!!evidence}
        onOpenChange={(open) => {
          if (!open) setEvidence(null);
        }}
      >
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Peer Evidence</SheetTitle>
            <SheetDescription>
              {evidence?.entity.name} · {evidence?.entity.key}
            </SheetDescription>
          </SheetHeader>
          {evidence && (
            <div className="sheet-stack">
              <section className="evidence-score">
                <p className="eyebrow">Description Similarity Score</p>
                <strong>{evidence.evidence.similarity}</strong>
                <p className="muted">
                  A similarity score, not a probability. Peers are ranked by
                  how closely their business descriptions match the target.
                </p>
              </section>
              <section>
                <h3>Classification and Geography</h3>
                <dl className="trace-values">
                  {Object.entries(evidence.evidence.classification).map(
                    ([key, v]) => (
                      <div key={key}>
                        <dt>{titleLabel(key)}</dt>
                        <dd>{v ? "Match" : "No Match"}</dd>
                      </div>
                    ),
                  )}
                  <div>
                    <dt>Country</dt>
                    <dd>
                      {evidence.evidence.country_match ? "Match" : "No Match"}
                    </dd>
                  </div>
                  <div>
                    <dt>Revenue Ratio (Peer / Target)</dt>
                    <dd>{evidence.evidence.revenue_ratio ?? "—"}</dd>
                  </div>
                </dl>
                <p className="muted">
                  Size and geography are evidence, not ranking inputs.
                </p>
              </section>
              <section>
                <h3>Limitations</h3>
                {evidence.evidence.limitations.length ? (
                  <ul>
                    {evidence.evidence.limitations.map((code) => (
                      <li key={code}>{code}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted">No limitations reported.</p>
                )}
                <Findings findings={evidence.findings} />
              </section>
              <Button
                variant="outline"
                onClick={() => {
                  setDetail(evidence.entity.key);
                  setEvidence(null);
                }}
              >
                Open Calculation Trace
              </Button>
            </div>
          )}
        </SheetContent>
      </Sheet>
      <CompanyDetail companyKey={detail} onClose={() => setDetail(null)} />
    </div>
  );
}
