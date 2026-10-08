import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";
import ThemeToggle from "../../components/common/ThemeToggle";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    document.title = "Log in | AI Data Analyst";
  }, []);

  function updateField(event) {
    setForm({ ...form, [event.target.name]: event.target.value });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(form);
      navigate(location.state?.from?.pathname || "/dashboard", { replace: true });
    } catch (requestError) {
      const status = requestError.response?.status;
      setError(status === 401
        ? "The email or password was not recognized. Check your details and try again."
        : "We couldn't sign you in right now. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-layout">
      <aside className="auth-aside">
        <div className="auth-aside-head">
          <Link to="/" className="auth-brand"><span className="auth-brand-mark" aria-hidden="true">A</span><span>AI Data Analyst<small>&amp; Decision Assistant</small></span></Link>
          <ThemeToggle />
        </div>
        <div className="auth-aside-content">
          <p className="eyebrow">YOUR DATA WORKSPACE</p>
          <h2>Turn your datasets into clearer decisions.</h2>
          <p className="auth-aside-copy">Turn your datasets into clear insights, intelligent answers, and data-driven decisions.</p>
          <ul className="auth-capabilities">
            <li><span aria-hidden="true">&#10003;</span>Analyze CSV &amp; Excel datasets</li>
            <li><span aria-hidden="true">&#10003;</span>Explore interactive analytics</li>
            <li><span aria-hidden="true">&#10003;</span>Ask questions about your data</li>
            <li><span aria-hidden="true">&#10003;</span>Generate AI-powered reports</li>
          </ul>
        </div>
        <div className="auth-data-visual" aria-hidden="true">
          <span className="auth-visual-caption">DATA &nbsp; / &nbsp; ANALYSIS &nbsp; / &nbsp; DECISIONS</span>
          <svg viewBox="0 0 600 150" preserveAspectRatio="none">
            <path className="auth-visual-track" d="M0 122H600M0 82H600M0 42H600" />
            <path className="auth-visual-line" d="M8 112C70 111 70 72 135 80S205 105 255 69 325 92 374 51 452 71 495 31 555 53 592 14" />
            <path className="auth-visual-link" d="M135 80 180 37 255 69 305 31 374 51 425 17 495 31 544 9" />
            <circle cx="135" cy="80" r="4" /><circle cx="255" cy="69" r="4" /><circle cx="374" cy="51" r="4" /><circle cx="495" cy="31" r="4" /><circle cx="592" cy="14" r="4" />
          </svg>
        </div>
        <Link to="/" className="auth-back-link">Back to home</Link>
      </aside>
      <section className="auth-main">
        <div className="auth-panel">
          <p className="eyebrow">WELCOME BACK</p>
          <h1>Welcome back</h1>
          <p className="auth-intro">Sign in to continue analyzing your data.</p>
          <form onSubmit={handleSubmit} className="auth-form">
            <label htmlFor="login-email">Email address<input id="login-email" name="email" type="email" autoComplete="email" value={form.email} onChange={updateField} required /></label>
            <label htmlFor="login-password">Password<span className="password-field"><input id="login-password" name="password" type={showPassword ? "text" : "password"} autoComplete="current-password" value={form.password} onChange={updateField} required /><button type="button" className="password-toggle" onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? "Hide" : "Show"}</button></span></label>
            <p className="recovery-note">Password recovery is not configured yet. Contact your workspace administrator if you need help.</p>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="button button-primary auth-submit" type="submit" disabled={submitting}>{submitting ? "Signing in..." : "Sign in"}</button>
          </form>
          <p className="auth-switch">New to the workspace? <Link to="/register">Create an account</Link></p>
        </div>
      </section>
    </main>
  );
}
