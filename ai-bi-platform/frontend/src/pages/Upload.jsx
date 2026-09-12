import React, { useEffect, useRef, useState } from "react";
import { api, count, msg } from "../api.js";

export default function Upload() {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [history, setHistory] = useState([]);
  const [logs, setLogs] = useState(null);
  const inputRef = useRef();

  const loadHistory = () =>
    api.get("/upload/history").then((r) => setHistory(r.data)).catch(() => {});

  useEffect(() => { loadHistory(); }, []);

  const send = async (file) => {
    if (!file) return;
    setBusy(true); setError(""); setResult(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const { data } = await api.post("/upload", form);
      setResult(data);
      loadHistory();
    } catch (e) {
      setError(msg(e, "The upload could not be processed."));
    } finally {
      setBusy(false);
    }
  };

  const showLogs = async (batchId) => {
    const { data } = await api.get(`/upload/${batchId}/logs`);
    setLogs({ batchId, entries: data });
  };

  return (
    <>
      <div
        className="drop"
        onClick={() => inputRef.current.click()}
        onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add("over"); }}
        onDragLeave={(e) => e.currentTarget.classList.remove("over")}
        onDrop={(e) => { e.preventDefault(); e.currentTarget.classList.remove("over"); send(e.dataTransfer.files[0]); }}
      >
        <b>{busy ? "Running the pipeline…" : "Drop a sales file here, or click to choose"}</b>
        <p>CSV or Excel. Needs at least a date, product, quantity and price column.</p>
        <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" hidden
               onChange={(e) => send(e.target.files[0])} />
      </div>

      {error && <div className="error">{error}</div>}

      {result && (
        <div className="ok">
          Loaded <b className="num">{count(result.rows_loaded)}</b> rows from {result.filename}
          {result.rows_rejected > 0 && <> · <span className="num">{result.rows_rejected}</span> rejected</>}
          {result.warnings?.length > 0 && (
            <ul style={{ margin: "8px 0 0 16px", padding: 0 }}>
              {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          )}
        </div>
      )}

      <div className="card" style={{ marginTop: 22 }}>
        <h3>Upload history</h3>
        {history.length === 0 && <p className="note">Nothing uploaded yet.</p>}
        {history.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>File</th><th>Status</th><th className="r">Loaded</th>
                <th className="r">Rejected</th><th>When</th><th></th>
              </tr>
            </thead>
            <tbody>
              {history.map((b) => (
                <tr key={b.batch_id}>
                  <td>{b.filename}</td>
                  <td><span className={`pill ${b.status}`}>{b.status}</span></td>
                  <td className="r">{count(b.rows_loaded)}</td>
                  <td className="r">{count(b.rows_rejected)}</td>
                  <td className="note num">{new Date(b.uploaded_at).toLocaleDateString("en-IN")}</td>
                  <td><button className="ghost" style={{ padding: "3px 9px", fontSize: 12 }}
                              onClick={() => showLogs(b.batch_id)}>Logs</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {logs && (
        <div className="card" style={{ marginTop: 18 }}>
          <h3>Pipeline log — batch {logs.batchId}</h3>
          <table>
            <thead><tr><th>Stage</th><th>Level</th><th>Message</th></tr></thead>
            <tbody>
              {logs.entries.map((l, i) => (
                <tr key={i}>
                  <td className="num">{l.stage}</td>
                  <td><span className="pill">{l.level}</span></td>
                  <td>{l.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
