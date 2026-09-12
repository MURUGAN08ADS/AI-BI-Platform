import React, { useEffect, useState } from "react";
import { Line } from "react-chartjs-2";
import { api, compact, msg } from "../api.js";

export default function Forecast() {
  const [periods, setPeriods] = useState(6);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = (n) => {
    setBusy(true); setError("");
    api.get(`/forecast?periods=${n}`)
      .then((r) => setData(r.data))
      .catch((e) => setError(msg(e, "Could not build a forecast.")))
      .finally(() => setBusy(false));
  };

  useEffect(() => { load(periods); }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  if (error) return <div className="error">{error}</div>;
  if (!data) return <p className="note spinner">Fitting the model…</p>;

  if (data.status === "insufficient_data") {
    return <div className="card"><h3>Not enough history</h3><p className="note">{data.message}</p></div>;
  }

  const histLabels = data.history.map((h) => `${h.month_name.slice(0, 3)} ${String(h.year).slice(2)}`);
  const fcLabels = data.forecast.map((f) => f.label);
  const labels = [...histLabels, ...fcLabels];
  const pad = new Array(histLabels.length - 1).fill(null);

  return (
    <>
      <div className="card">
        <h3>Revenue forecast</h3>
        <div style={{ display: "flex", gap: 10, alignItems: "flex-end", marginBottom: 16 }}>
          <div style={{ width: 150 }}>
            <label htmlFor="p">Months ahead</label>
            <input id="p" type="number" min="1" max="24" value={periods}
                   onChange={(e) => setPeriods(Number(e.target.value))} />
          </div>
          <button className="primary" onClick={() => load(periods)} disabled={busy}>
            {busy ? "Working…" : "Update"}
          </button>
        </div>

        <div className="chart-box" style={{ height: 320 }}>
          <Line
            options={{
              responsive: true, maintainAspectRatio: false,
              plugins: { legend: { labels: { font: { family: "Inter", size: 11 }, boxWidth: 10 } } },
              scales: {
                x: { grid: { display: false }, ticks: { font: { family: "IBM Plex Mono", size: 10 } } },
                y: { grid: { color: "#e3e0d8" }, ticks: { font: { family: "IBM Plex Mono", size: 10 } } },
              },
            }}
            data={{
              labels,
              datasets: [
                { label: "Actual", data: data.history.map((h) => h.revenue),
                  borderColor: "#2b3a8f", backgroundColor: "rgba(43,58,143,.08)",
                  fill: true, tension: .3, pointRadius: 2 },
                { label: "Forecast",
                  data: [...pad, data.history.at(-1)?.revenue, ...data.forecast.map((f) => f.predicted_revenue)],
                  borderColor: "#b4762a", borderDash: [6, 4], tension: .3, pointRadius: 3 },
                { label: "Upper bound",
                  data: [...pad, data.history.at(-1)?.revenue, ...data.forecast.map((f) => f.upper_bound)],
                  borderColor: "rgba(180,118,42,.28)", pointRadius: 0, borderWidth: 1 },
                { label: "Lower bound",
                  data: [...pad, data.history.at(-1)?.revenue, ...data.forecast.map((f) => f.lower_bound)],
                  borderColor: "rgba(180,118,42,.28)", pointRadius: 0, borderWidth: 1 },
              ],
            }}
          />
        </div>
      </div>

      <div className="grid two">
        <div className="card">
          <h3>Projected months</h3>
          <table>
            <thead>
              <tr><th>Month</th><th className="r">Forecast</th><th className="r">Range</th></tr>
            </thead>
            <tbody>
              {data.forecast.map((f) => (
                <tr key={f.label}>
                  <td className="num">{f.label}</td>
                  <td className="r">{compact(f.predicted_revenue)}</td>
                  <td className="r note">{compact(f.lower_bound)} – {compact(f.upper_bound)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <h3>Model</h3>
          <p className="note" style={{ marginTop: 0 }}>{data.model}</p>
          <table>
            <tbody>
              <tr><td>Fit (R²)</td><td className="r">{data.metrics.r2}</td></tr>
              <tr><td>RMSE</td><td className="r">{compact(data.metrics.rmse)}</td></tr>
              <tr><td>Trend per month</td><td className="r">{compact(data.metrics.trend_per_month)}</td></tr>
              <tr><td>Months of history</td><td className="r">{data.metrics.history_points}</td></tr>
            </tbody>
          </table>
          <p className="note" style={{ marginTop: 12, fontSize: 12.5 }}>
            The shaded range is a 95% interval from in-sample error. Treat short
            histories with caution — the model cannot see events it has no data for.
          </p>
        </div>
      </div>
    </>
  );
}
