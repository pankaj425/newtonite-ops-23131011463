import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../auth.jsx";

export default function Layout() {
  const { user, memberships, logout } = useAuth();
  const navigate = useNavigate();

  function onLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">Operations Under Pressure</div>
        <nav>
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/items">Work items</NavLink>
        </nav>
        <div>
          <span className="who">
            {user?.name} · {memberships.length} team{memberships.length === 1 ? "" : "s"}
          </span>{" "}
          <button type="button" className="ghost" onClick={onLogout}>
            Log out
          </button>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
