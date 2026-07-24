import { NavLink, Outlet } from "react-router-dom";

// App shell: sidebar navigation + routed content area.
export default function DashboardLayout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">AI Ops Platform</div>
        <nav className="nav">
          <NavLink to="/" end>
            Overview
          </NavLink>
          {/* Feature links added as pages are built:
              SLA Risk · Root Cause · Client Health */}
        </nav>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
