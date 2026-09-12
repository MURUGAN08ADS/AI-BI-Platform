import React from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";

const PAGES = {
  "/":         ["Overview",  "Revenue, profit and performance across the warehouse"],
  "/upload":   ["Data",      "Upload a dataset and watch it move through the pipeline"],
  "/ask":      ["Ask",       "Question the warehouse in plain English"],
  "/forecast": ["Forecast",  "Projected revenue from the historical trend"],
};

export default function Shell({ children }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("bi_user") || "{}");
  const [title, subtitle] = PAGES[pathname] || PAGES["/"];

  const signOut = () => {
    localStorage.removeItem("bi_token");
    localStorage.removeItem("bi_user");
    navigate("/login");
  };

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <h1>Ledger</h1>
          <span>BI &amp; Data Warehouse</span>
        </div>
        <nav className="nav">
          <NavLink to="/" end>Overview <span className="k">01</span></NavLink>
          <NavLink to="/upload">Data <span className="k">02</span></NavLink>
          <NavLink to="/ask">Ask <span className="k">03</span></NavLink>
          <NavLink to="/forecast">Forecast <span className="k">04</span></NavLink>
        </nav>
        <div className="sidebar-foot">
          <b>{user.email || "Signed in"}</b>
          {user.role} access
          <button onClick={signOut}>Sign out</button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </header>
        <div className="content">{children}</div>
      </main>
    </div>
  );
}
