import React, { useRef, useState } from "react";
import { api, msg } from "../api.js";

const SUGGESTIONS = [
  "What is the best-selling product?",
  "Show revenue by month",
  "Which region made the most profit?",
  "Who are the top 5 customers?",
  "Compare revenue between Chennai and Mumbai",
];

export default function Chat() {
  const [log, setLog] = useState([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef();

  const ask = async (text) => {
    const q = (text ?? question).trim();
    if (!q || busy) return;
    setLog((l) => [...l, { role: "user", text: q }]);
    setQuestion(""); setBusy(true);
    try {
      const { data } = await api.post("/chat", { question: q });
      setLog((l) => [...l, { role: "assistant", ...data }]);
    } catch (e) {
      setLog((l) => [...l, { role: "assistant", answer: msg(e, "The assistant is unavailable."), error: true }]);
    } finally {
      setBusy(false);
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 60);
    }
  };

  return (
    <div className="card">
      <h3>Ask the warehouse</h3>

      <div className="chat-log">
        {log.length === 0 && (
          <p className="note">
            Ask a question in plain English. The assistant writes the SQL, runs it
            read-only against the warehouse, and shows you exactly what it ran.
          </p>
        )}

        {log.map((m, i) =>
          m.role === "user" ? (
            <div className="msg user" key={i}>
              <div className="who">You</div>
              <div className="bubble">{m.text}</div>
            </div>
          ) : (
            <div className="msg" key={i}>
              <div className="who">Assistant</div>
              <div className="bubble">
                {m.answer}
                {m.blocked && (
                  <div className="blocked">
                    Query blocked by the SQL guard — it was never executed.
                  </div>
                )}
                {m.sql && (
                  <details className="sql">
                    <summary>View the SQL that ran</summary>
                    <pre>{m.sql}</pre>
                  </details>
                )}
                {m.rows?.length > 0 && (
                  <details className="sql">
                    <summary>View {m.rows.length} result row(s)</summary>
                    <div style={{ overflowX: "auto", marginTop: 8 }}>
                      <table>
                        <thead><tr>{m.columns.map((c) => <th key={c} className="r">{c}</th>)}</tr></thead>
                        <tbody>
                          {m.rows.slice(0, 15).map((r, ri) => (
                            <tr key={ri}>{r.map((v, ci) => <td key={ci} className="r">{String(v)}</td>)}</tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </details>
                )}
              </div>
            </div>
          )
        )}
        {busy && <div className="msg"><div className="who">Assistant</div>
          <div className="bubble spinner">Writing the query…</div></div>}
        <div ref={endRef} />
      </div>

      <form className="chat-form" onSubmit={(e) => { e.preventDefault(); ask(); }}>
        <input type="text" value={question} placeholder="e.g. Which product sold the most last quarter?"
               onChange={(e) => setQuestion(e.target.value)} />
        <button className="primary" disabled={busy || !question.trim()}>Ask</button>
      </form>

      <div className="suggestions">
        {SUGGESTIONS.map((s) => (
          <button key={s} onClick={() => ask(s)} disabled={busy}>{s}</button>
        ))}
      </div>
    </div>
  );
}
