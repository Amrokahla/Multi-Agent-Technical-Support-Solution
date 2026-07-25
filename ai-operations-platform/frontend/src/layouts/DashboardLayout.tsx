import { NavLink, Outlet } from "react-router-dom";

// App shell: control-room rail + routed content. Workforce is feature one of the
// platform; the greyed items are the roadmap, shown so the scope reads clearly.
export default function DashboardLayout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">◇</div>
          <div className="brand-name">
            AI Operations
            <span>Support Intelligence</span>
          </div>
        </div>

        <div>
          <p className="nav-label">Operate</p>
          <nav className="nav">
            <NavLink to="/" end>
              Workforce
            </NavLink>
            <div className="nav-ghost">
              SLA Risk <span className="soon">soon</span>
            </div>
            <div className="nav-ghost">
              Root Cause <span className="soon">soon</span>
            </div>
            <div className="nav-ghost">
              Client Health <span className="soon">soon</span>
            </div>
          </nav>
        </div>

        <div className="sidebar-foot">
          Zendesk dataset
          <br />
          8,000 tickets · 45 agents
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
