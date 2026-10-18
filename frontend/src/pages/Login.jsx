import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth.jsx";

const DEMO = [
  ["admin@newtonite.dev", "admin in Payments, lead in Support"],
  ["lead@newtonite.dev", "lead in Payments"],
  ["member@newtonite.dev", "member in Payments and Support"],
  ["viewer@newtonite.dev", "viewer in Payments"],
  ["other@newtonite.dev", "member in Compliance (other team)"],
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("member@newtonite.dev");
  const [password, setPassword] = useState("Password123!");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err.message || "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <div className="panel">
        <h2>Operations Under Pressure</h2>
        <p className="muted">Sign in with a demo account to continue.</p>
        {error && <div className="alert error">{error}</div>}
        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          <button type="submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
      <div className="panel">
        <h3>Demo accounts</h3>
        <p className="muted">
          All demo accounts use the password <code>Password123!</code>
        </p>
        <ul className="demo-list">
          {DEMO.map(([mail, role]) => (
            <li key={mail}>
              <code>{mail}</code> — {role}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
