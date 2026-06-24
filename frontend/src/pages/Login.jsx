import { useState } from "react";
import { useLocation, useNavigate, Link } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export default function Login() {
  const { login, signup } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from || "/";

  const [mode, setMode] = useState("login"); // "login" | "signup"
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    if (!username.trim() || !password) {
      setError("Enter a username and password.");
      return;
    }
    setSubmitting(true);
    try {
      if (mode === "login") await login(username.trim(), password);
      else await signup(username.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  return (
    <section className="page-narrow auth-page">
      <Link to="/" className="back">
        ← all stories
      </Link>
      <h1>{mode === "login" ? "Log in" : "Sign up"}</h1>

      <div className="auth-toggle">
        <button
          type="button"
          className={"seg-btn" + (mode === "login" ? " active" : "")}
          onClick={() => {
            setMode("login");
            setError(null);
          }}
        >
          Log in
        </button>
        <button
          type="button"
          className={"seg-btn" + (mode === "signup" ? " active" : "")}
          onClick={() => {
            setMode("signup");
            setError(null);
          }}
        >
          Sign up
        </button>
      </div>

      <form className="add-form auth-form" onSubmit={handleSubmit}>
        <label className="field-label">Username</label>
        <input
          className="field"
          type="text"
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />

        <label className="field-label">Password</label>
        <input
          className="field"
          type="password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {error && <p className="error">{error}</p>}

        <div className="form-actions">
          <button type="submit" className="primary-btn" disabled={submitting}>
            {submitting
              ? mode === "login"
                ? "Logging in…"
                : "Signing up…"
              : mode === "login"
              ? "Log in"
              : "Sign up"}
          </button>
        </div>
      </form>
    </section>
  );
}
