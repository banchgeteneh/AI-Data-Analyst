import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";
import ThemeToggle from "../../components/common/ThemeToggle";

export default function RegisterPage() {
  const { register, login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", confirmPassword: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    document.title = "Create account | AI Data Analyst";
  }, []);

  const passwordScore = [
    form.password.length >= 8,
    form.password.length >= 12,
    /[A-Z]/.test(form.password) && /[a-z]/.test(form.password),
    /\d/.test(form.password),
    /[^A-Za-z0-9]/.test(form.password),
  ].filter(Boolean).length;
  const passwordStrength = passwordScore < 3 ? "Building" : passwordScore < 4 ? "Good" : "Strong";

  function updateField(event) {
    setForm({ ...form, [event.target.name]: event.target.value });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSuccess("");
    if (form.password !== form.confirmPassword) {
      setError("Your passwords do not match. Check both fields and try again.");
      return;
    }
    setSubmitting(true);
    let accountCreated = false;
    try {
      await register({ name: form.name, email: form.email, password: form.password });
      accountCreated = true;
      setSuccess("Account created. Opening your workspace...");
      await login({ email: form.email, password: form.password });
      navigate("/dashboard", { replace: true });
    } catch (requestError) {
      const status = requestError.response?.status;
      setError(status === 409
        ? "An account already uses that email address. Sign in or use another email."
        : accountCreated
          ? "Your account was created, but we couldn't sign you in. Please log in."
          : "We couldn't create your account right now. Check your details and try again.");
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
          <p className="eyebrow">START WITH YOUR DATA</p>
          <h2>Turn your datasets into clearer decisions.</h2>
          <p className="auth-aside-copy">Start turning your data into actionable insights with analysis, interactive charts, and AI when available.</p>
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
          <p className="eyebrow">GET STARTED</p>
          <h1>Create your account</h1>
          <p className="auth-intro">Start turning your data into actionable insights.</p>
          <form onSubmit={handleSubmit} className="auth-form">
            <label htmlFor="register-name">Full name<input id="register-name" name="name" autoComplete="name" maxLength="100" value={form.name} onChange={updateField} required /></label>
            <label htmlFor="register-email">Email address<input id="register-email" name="email" type="email" autoComplete="email" value={form.email} onChange={updateField} required /></label>
            <label htmlFor="register-password">Password<span className="password-field"><input id="register-password" name="password" type={showPassword ? "text" : "password"} autoComplete="new-password" minLength="8" maxLength="72" value={form.password} onChange={updateField} required /><button type="button" className="password-toggle" onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? "Hide" : "Show"}</button></span></label>
            {form.password && <div className="password-strength" aria-live="polite"><div className="strength-track"><span data-strength={passwordScore} /></div><span>Password strength: {passwordStrength}</span></div>}
            <label htmlFor="register-confirm-password">Confirm password<span className="password-field"><input id="register-confirm-password" name="confirmPassword" type={showConfirmation ? "text" : "password"} autoComplete="new-password" value={form.confirmPassword} onChange={updateField} required /><button type="button" className="password-toggle" onClick={() => setShowConfirmation((visible) => !visible)} aria-label={showConfirmation ? "Hide password confirmation" : "Show password confirmation"}>{showConfirmation ? "Hide" : "Show"}</button></span></label>
            {error && <p className="form-error" role="alert">{error}</p>}
            {success && <p className="form-success" role="status">{success}</p>}
            <button className="button button-primary auth-submit" type="submit" disabled={submitting}>{submitting ? "Creating account..." : "Create account"}</button>
          </form>
          <p className="auth-switch">Already registered? <Link to="/login">Sign in</Link></p>
        </div>
      </section>
    </main>
  );
}
