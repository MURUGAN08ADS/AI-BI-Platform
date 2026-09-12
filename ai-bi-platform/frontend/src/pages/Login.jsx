import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, msg } from "../api.js";

export default function Login() {
  const [mode, setMode] = useState("login");   // login | register
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("analyst");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const path = mode === "login" ? "/auth/login" : "/auth/register";
      const body = mode === "login" ? { email, password } : { email, password, role };
      const { data } = await api.post(path, body);
      localStorage.setItem("bi_token", data.access_token);
      localStorage.setItem("bi_user", JSON.stringify({ email: data.email, role: data.role }));
      navigate("/");
    } catch (err) {
      setError(msg(err, "Could not sign in."));
      setBusy(false);
    }
  };

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <h1>Ledger</h1>
        <p className="sub">
          {mode === "login"
            ? "Sign in to your business intelligence workspace."
            : "Create an account to start loading data."}
        </p>

        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" value={email} required
                   onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="pw">Password</label>
            <input id="pw" type="password" value={password} required minLength={8}
                   onChange={(e) => setPassword(e.target.value)} />
          </div>
          {mode === "register" && (
            <div className="field">
              <label htmlFor="role">Access level</label>
              <select id="role" value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="analyst">Analyst — upload and explore</option>
                <option value="viewer">Viewer — read dashboards</option>
                <option value="admin">Admin — full access</option>
              </select>
            </div>
          )}

          <button className="primary" style={{ width: "100%" }} disabled={busy}>
            {busy ? "Working…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        {error && <div className="error">{error}</div>}

        <p className="swap">
          {mode === "login" ? "No account yet? " : "Already registered? "}
          <button onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
            {mode === "login" ? "Create one" : "Sign in"}
          </button>
        </p>
      </div>
    </div>
  );
}
