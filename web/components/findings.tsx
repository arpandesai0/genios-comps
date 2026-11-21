import type { Finding } from "@/lib/api-types";
import { Badge } from "@/components/ui/badge";
export function Findings({ findings }: { findings: Finding[] }) {
  return findings.length ? (
    <ul className="findings-list">
      {findings.map((f, i) => (
        <li key={`${f.code}-${i}`}>
          <div className="badge-row">
            <Badge className={`severity-${f.severity}`}>{f.severity}</Badge>
            <strong>{f.code}</strong>
            {f.source === "derived" && (
              <Badge className="derived">model-derived</Badge>
            )}
          </div>
          <p>{f.message}</p>
          <small className="muted">
            Fields: {f.fields.join(", ") || "—"} · Affects:{" "}
            {f.affects.join(", ") || "—"}
          </small>
        </li>
      ))}
    </ul>
  ) : (
    <p className="muted">No findings.</p>
  );
}
