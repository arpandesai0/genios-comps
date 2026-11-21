"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { BarChart3, Database, Layers3, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [dark, setDark] = useState(false);
  return (
    <div className={dark ? "app-shell dark" : "app-shell"}>
      <aside className="sidebar">
        <Link href="/" className="brand">
          <span className="brand-icon">
            <Layers3 size={22} />
          </span>
          <span>
            genios<span className="brand-sub">FINANCE WORKSPACE</span>
          </span>
        </Link>
        <div className="nav-label">RESEARCH</div>
        <nav aria-label="Main navigation">
          <Link
            className={path === "/" ? "nav-link active" : "nav-link"}
            href="/"
            aria-current={path === "/" ? "page" : undefined}
          >
            <BarChart3 size={18} />
            Compare
          </Link>
          <Link
            className={path === "/data" ? "nav-link active" : "nav-link"}
            href="/data"
            aria-current={path === "/data" ? "page" : undefined}
          >
            <Database size={18} />
            Data
          </Link>
        </nav>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span>
            Workspace{" "}
            <span className="breadcrumb">
              / {path === "/data" ? "Data" : "Compare"}
            </span>
          </span>
          <div className="flex items-center gap-2">
            <span className="environment">
              {process.env.NEXT_PUBLIC_USE_MOCKS !== "0"
                ? "Synthetic mock dataset"
                : "Connected API"}
            </span>
            <Button
              variant="outline"
              size="icon"
              onClick={() => {
                setDark(!dark);
                document.documentElement.classList.toggle("dark", !dark);
              }}
              aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
            >
              {dark ? <Sun size={16} /> : <Moon size={16} />}
            </Button>
          </div>
        </header>
        <main>{children}</main>
        <footer>
          Genios Comps{" "}
          <span>
            Financial values in USD millions · Multiples as reported by the API
          </span>
        </footer>
      </div>
    </div>
  );
}
