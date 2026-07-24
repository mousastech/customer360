import { Suspense, lazy } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Users, BarChart3, FileCog } from "lucide-react";
import { api } from "./api/client";
import GenieWidget from "./components/GenieWidget";

// Code-split routes to keep the initial bundle small.
const Customers = lazy(() => import("./pages/Customers"));
const CustomerDetail = lazy(() => import("./pages/CustomerDetail"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Reports = lazy(() => import("./pages/Reports"));

function TopBar() {
  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: api.config,
    staleTime: 5 * 60_000,
  });
  const email = config?.user_email ?? "…";
  const host = config?.databricks_host?.replace(/^https?:\/\//, "") ?? "";
  const initials = email
    .split("@")[0]
    .split(/[.\-_]/)
    .map((s) => s[0]?.toUpperCase())
    .slice(0, 2)
    .join("");
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-dot" />
        Customer&nbsp;360 <span style={{ color: "var(--text-muted)", fontWeight: 500 }}>· Acme Retail</span>
      </div>
      <div className="topbar-right">
        {host && <span className="ws-badge">{host}</span>}
        <span className="user-chip">
          <span className="avatar">{initials || "?"}</span>
          {email}
        </span>
      </div>
    </header>
  );
}

function SideBar() {
  return (
    <nav className="sidebar">
      <NavLink to="/customers" className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
        <Users size={17} /> Customers
      </NavLink>
      <NavLink to="/dashboard" className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
        <BarChart3 size={17} /> Dashboard
      </NavLink>
      <NavLink to="/reports" className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
        <FileCog size={17} /> Reports
      </NavLink>
    </nav>
  );
}

export default function App() {
  return (
    <div className="shell">
      <TopBar />
      <SideBar />
      <main className="content">
        <Suspense fallback={<div className="center-load"><span className="spinner" /></div>}>
          <Routes>
            <Route path="/" element={<Navigate to="/customers" replace />} />
            <Route path="/customers" element={<Customers />} />
            <Route path="/customers/:id" element={<CustomerDetail />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="*" element={<div className="empty">Page not found</div>} />
          </Routes>
        </Suspense>
      </main>
      <GenieWidget />
    </div>
  );
}
