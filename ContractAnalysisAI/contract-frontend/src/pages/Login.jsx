import React, { useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { login } from "../services/orchestrator";
import { setToken } from "../services/auth";
import "../styles/global.css";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const recall = location.state?.from || "/upload";

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await login(username, password);
      setToken(data.access_token);
      navigate(recall, { replace: true });
    } catch (err) {
      console.error("Login error", err);
      setError("Invalid credentials or server error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="homepage" style={{ justifyContent: "center", alignItems: "center" }}>
      <form className="login-card" onSubmit={handleSubmit}>
        <h2>Member Access</h2>
        <p className="muted">Authenticate to access orchestration features.</p>
        <label>
          Username
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && <p className="error-text">{error}</p>}
        <button type="submit" className="primary-btn" disabled={loading}>
          {loading ? "Signing in..." : "Sign In"}
        </button>
        <p className="muted" style={{ marginTop: "16px" }}>
          Need a hint? Check the credentials in <code>.env</code>.
        </p>
        <Link to="/" className="secondary-btn" style={{ marginTop: "12px", textAlign: "center" }}>
          Back to Home
        </Link>
      </form>
    </div>
  );
}
