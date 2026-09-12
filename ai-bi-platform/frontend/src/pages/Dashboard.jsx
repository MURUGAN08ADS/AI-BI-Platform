import React, { useEffect, useState } from "react";
import { Line, Bar, Doughnut } from "react-chartjs-2";
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, ArcElement, Tooltip, Legend, Filler,
} from "chart.js";
import { Link } from "react-router-dom";
import { api, compact, count, msg, rupees } from "../api.js";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement,
                 BarElement, ArcElement, Tooltip, Legend, Filler);

const INK = "#14181f", INDIGO = "#2b3a8f", OCHRE = "#b4762a", RULE = "#e3e0d8";
const SERIES = [INDIGO, OCHRE, "#1f6f4a", "#a32b2b", "#5c6472", "#7a5ea8"];

const chartBase = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { labels: { font: { family: "Inter", size: 11 }, color: INK, boxWidth: 10 } },
    tooltip: { bodyFont: { family: "IBM Plex Mono", size: 12 } },
  },
  scales: {
    x: { grid: { display: false }, ticks: { font: { family: "IBM Plex Mono", size: 10 }, color: "#5c6472" } },
    y: { grid: { color: RULE }, ticks: { font: { family: "IBM Plex Mono", size: 10 }, color: "#5c6472" } },
  },
};

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get("/analytics/kpis"),
      api.get("/analytics/monthly"),
      api.get("/analytics/products?limit=8"),
      api.get("/analytics/regions"),
      api.get("/analytics/categories"),
      api.get("/analytics/customers?limit=8"),
      api.get("/analytics/insights"),
    ])
      .then(([k, m, p, r, c, cu, i]) =>
        setData({
          kpis: k.data, monthly: m.data, products: p.data,
          regions: r.data, categories: c.data, customers: cu.data, insights: i.data,
        }))
      .catch((e) => setError(msg(e, "Could not load analytics.")));
  }, []);

  if (error) return <div className="error">{error}</div>;
  if (!data) return <p className="note spinner">Loading the warehouse…</p>;

  const { kpis, monthly, products, regions, categories, customers, insights } = data;

  if (!monthly.length) {
    return (
      <div className="card" style={{ textAlign: "center", padding: "48px 24px" }}>
        <h3 style={{ border: "none" }}>The warehouse is empty</h3>
        <p className="note">Upload a sales dataset and the dashboards will fill in.</p>
        <Link to="/upload"><button className="primary" style={{ marginTop: 12 }}>Upload data</button></Link>
      </div>
    );
  }

  const labels = monthly.map((m) => `${m.month_name.slice(0, 3)} ${String(m.year).slice(2)}`);

  return (
    <>
      {/* KPI ledger — figures right-aligned and monospaced, ruled like a book */}
      <section className="ledger">
        <div className="ledger-row">
          <Kpi label="Total revenue" value={compact(kpis.total_revenue)}
               delta={`${kpis.growth_rate >= 0 ? "▲" : "▼"} ${Math.abs(kpis.growth_rate)}% vs last month`}
               dir={kpis.growth_rate >= 0 ? "up" : "down"} />
          <Kpi label="Total profit" value={compact(kpis.total_profit)}
               delta={`${kpis.profit_margin}% margin`} />
          <Kpi label="Orders" value={count(kpis.orders)} />
        </div>
        <div className="ledger-row">
          <Kpi label="Customers" value={count(kpis.customers)} />
          <Kpi label="Units sold" value={count(kpis.units_sold)} />
          <Kpi label="Average order" value={rupees(kpis.avg_order_value)} />
        </div>
      </section>

      <div className="grid two">
        <div className="card">
          <h3>Revenue and profit by month</h3>
          <div className="chart-box">
            <Line
              options={chartBase}
              data={{
                labels,
                datasets: [
                  { label: "Revenue", data: monthly.map((m) => m.revenue), borderColor: INDIGO,
                    backgroundColor: "rgba(43,58,143,.08)", fill: true, tension: .3, pointRadius: 2 },
                  { label: "Profit", data: monthly.map((m) => m.profit), borderColor: OCHRE,
                    backgroundColor: "rgba(180,118,42,.08)", fill: true, tension: .3, pointRadius: 2 },
                ],
              }}
            />
          </div>
        </div>

        <div className="card">
          <h3>Revenue by region</h3>
          <div className="chart-box">
            <Doughnut
              options={{ ...chartBase, scales: {}, cutout: "58%" }}
              data={{
                labels: regions.map((r) => r.region),
                datasets: [{ data: regions.map((r) => r.revenue), backgroundColor: SERIES,
                             borderColor: "#fff", borderWidth: 2 }],
              }}
            />
          </div>
        </div>
      </div>

      <div className="grid two">
        <div className="card">
          <h3>Top products by revenue</h3>
          <div className="chart-box">
            <Bar
              options={{ ...chartBase, indexAxis: "y",
                         plugins: { ...chartBase.plugins, legend: { display: false } } }}
              data={{
                labels: products.map((p) => p.product_name),
                datasets: [{ data: products.map((p) => p.revenue), backgroundColor: INDIGO,
                             borderRadius: 2, barThickness: 14 }],
              }}
            />
          </div>
        </div>

        <div className="card">
          <h3>Category performance</h3>
          <div className="chart-box">
            <Bar
              options={chartBase}
              data={{
                labels: categories.map((c) => c.category),
                datasets: [
                  { label: "Revenue", data: categories.map((c) => c.revenue), backgroundColor: INDIGO, borderRadius: 2 },
                  { label: "Profit", data: categories.map((c) => c.profit), backgroundColor: OCHRE, borderRadius: 2 },
                ],
              }}
            />
          </div>
        </div>
      </div>

      <div className="grid two">
        <div className="card">
          <h3>Top customers</h3>
          <table>
            <thead>
              <tr><th>Customer</th><th>Segment</th><th className="r">Revenue</th><th className="r">Orders</th></tr>
            </thead>
            <tbody>
              {customers.map((c) => (
                <tr key={c.customer_name}>
                  <td>{c.customer_name}</td>
                  <td className="note">{c.segment}</td>
                  <td className="r">{rupees(c.revenue)}</td>
                  <td className="r">{count(c.orders)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <h3>What the data shows</h3>
          {insights.length === 0 && <p className="note">Not enough data for insights yet.</p>}
          {insights.map((i, n) => (
            <div key={n} className={`insight ${i.type}`}>
              <div className="tick" />
              <div><b>{i.title}</b><p>{i.detail}</p></div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function Kpi({ label, value, delta, dir }) {
  return (
    <div className="kpi">
      <span className="label">{label}</span>
      <span className="value num">{value}</span>
      {delta && <span className={`delta num ${dir || ""}`}>{delta}</span>}
    </div>
  );
}
