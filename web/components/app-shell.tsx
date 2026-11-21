"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  BarChart3,
  Database,
  Layers3,
  Moon,
  PanelLeft,
  Sun,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const destinations = [
  { href: "/", name: "Compare", icon: BarChart3 },
  { href: "/data", name: "Data", icon: Database },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [dark, setDark] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const current = destinations.find(({ href }) => href === path)?.name;
  return (
    <div
      className={`app-shell${dark ? " dark" : ""}${collapsed ? " sidebar-collapsed" : ""}`}
    >
      <header className="topbar">
        <div className="topbar-location">
          <Button
            className="sidebar-toggle"
            variant="ghost"
            size="icon"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
            aria-controls="workspace-sidebar"
            onClick={() => setCollapsed(!collapsed)}
          >
            <PanelLeft size={17} />
          </Button>
          <Link href="/" className="brand" aria-label="Genios home">
            <span className="brand-icon">
              <Layers3 size={15} />
            </span>
            Genios
          </Link>
          {current && (
            <span className="breadcrumb">
              <span aria-hidden="true">/</span> {current}
            </span>
          )}
        </div>
        <div className="topbar-actions">
          <span className="environment">
            {process.env.NEXT_PUBLIC_USE_MOCKS !== "0"
              ? "Synthetic mock data"
              : "API mode"}
          </span>
          <Button
            variant="ghost"
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
      <aside className="sidebar" id="workspace-sidebar">
        <nav aria-label="Main navigation">
          {destinations.map(({ href, name, icon: Icon }) => (
            <Link
              key={href}
              className={`nav-link${path === href ? " active" : ""}`}
              href={href}
              aria-current={path === href ? "page" : undefined}
              aria-label={name}
              title={collapsed ? name : undefined}
            >
              <Icon size={17} aria-hidden="true" />
              <span>{name}</span>
            </Link>
          ))}
        </nav>
      </aside>
      <div className="workspace">
        <main>{children}</main>
      </div>
    </div>
  );
}
