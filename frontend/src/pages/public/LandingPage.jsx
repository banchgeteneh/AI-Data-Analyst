import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";
import ThemeToggle from "../../components/common/ThemeToggle";

const features = [
  { mark: "01", title: "Automated data analysis", text: "Upload CSV or Excel files and surface descriptive statistics, data-quality signals, and useful comparisons." },
  { mark: "02", title: "Interactive analytics", text: "Explore revenue, category, region, and correlation views built from your dataset." },
  { mark: "03", title: "Dataset-aware AI", text: "Ask questions against the analysis context, with uncertainty called out when evidence is limited." },
  { mark: "04", title: "Useful recommendations", text: "Turn supported observations into practical next steps, without confusing correlation for cause." },
  { mark: "05", title: "Professional reports", text: "Generate structured reports with findings, trends, business insights, and recommendations." },
  { mark: "06", title: "Data quality", text: "See missing values, duplicate rows, and columns that need a closer look." },
];

const steps = ["Upload", "Analyze", "Ask AI", "Decide"];

const faqs = [
  ["What file formats can I upload?", "The current upload workflow supports CSV and Excel (.xlsx) files, subject to the configured file-size limit."],
  ["What does the platform analyze?", "It calculates dataset dimensions, missing values, duplicates, numeric statistics, categorical summaries, correlations, and chart aggregates."],
  ["Can I ask questions about my dataset?", "Yes. The dataset assistant uses the available analysis context to answer questions and supports follow-up conversation."],
  ["Can I generate reports?", "Yes. Generate a structured report from the available analysis and download it as Markdown."],
  ["Is my data associated with my account?", "Datasets are stored with an owning account, and dataset APIs check ownership before returning, analyzing, or deleting a dataset."],
  ["What if the AI service is unavailable?", "AI requests may be temporarily unavailable. The interface offers retry, while upload and non-AI analysis remain separate workflows."],
];

function ProductPreview() {
  return (
    <div className="preview-window" aria-label="Illustrative product preview using sample data">
      <div className="preview-topbar"><span className="preview-brand-mark">A</span><strong>Workspace</strong><span className="preview-tag">Illustrative sample</span></div>
      <div className="preview-body">
        <div className="preview-sidebar"><i /><i /><i /><i /></div>
        <div className="preview-content">
          <div className="preview-title-row"><div><span>DATASET OVERVIEW</span><strong>Quarterly sales</strong></div><span className="preview-file">CSV</span></div>
          <div className="preview-metrics"><div><span>Rows</span><strong>1,284</strong><small>Sample</small></div><div><span>Columns</span><strong>12</strong><small>Sample</small></div><div><span>Missing</span><strong>0.8%</strong><small>Sample</small></div></div>
          <div className="preview-chart-card"><div className="preview-card-title"><strong>Revenue by month</strong><span>Sample values</span></div><div className="preview-chart"><div className="preview-grid-lines"><i /><i /><i /><i /></div><svg viewBox="0 0 520 145" role="img" aria-label="Illustrative ascending revenue line chart"><path d="M8 118 C60 106 76 90 120 98 S185 72 225 78 S280 45 326 64 S398 29 440 38 S489 12 512 20" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" /><path d="M8 118 C60 106 76 90 120 98 S185 72 225 78 S280 45 326 64 S398 29 440 38 S489 12 512 20" fill="none" stroke="transparent" strokeWidth="16" /></svg></div><div className="preview-months"><span>Jan</span><span>Mar</span><span>May</span><span>Jul</span><span>Sep</span><span>Nov</span></div></div>
          <div className="preview-bottom"><div><span>AI INSIGHT · SAMPLE</span><p>Revenue is higher in the final period shown. Check seasonality before drawing conclusions.</p></div><div><span>NEXT STEP</span><p>Compare margin by product.</p></div></div>
        </div>
      </div>
    </div>
  );
}

export default function LandingPage() {
  const { isAuthenticated } = useAuth();
  const { pathname } = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeSection, setActiveSection] = useState("home");
  const menuButtonRef = useRef(null);

  useEffect(() => {
    document.title = "AI Data Analyst & Decision Assistant | Turn Data Into Decisions";
    const sectionByPath = { "/features": "features", "/how-it-works": "how-it-works", "/about": "about", "/faq": "faq" };
    const target = sectionByPath[pathname];
    if (target) requestAnimationFrame(() => document.getElementById(target)?.scrollIntoView());
    const sections = ["home", "features", "how-it-works", "about", "faq"]
      .map((id) => document.getElementById(id))
      .filter(Boolean);
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible) setActiveSection(visible.target.id);
    }, { rootMargin: "-20% 0px -65% 0px", threshold: [0, 0.2, 0.5] });
    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, [pathname]);

  useEffect(() => {
    if (!menuOpen) return undefined;
    function handleEscape(event) {
      if (event.key === "Escape") {
        setMenuOpen(false);
        menuButtonRef.current?.focus();
      }
    }
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [menuOpen]);

  function closeMenu() {
    setMenuOpen(false);
  }

  const accountHref = isAuthenticated ? "/dashboard" : "/register";

  return (
    <div className="public-site">
      <header className="public-header">
        <a className="brand-lockup" href="#home" onClick={closeMenu} aria-label="AI Data Analyst home">
          <span className="brand-mark" aria-hidden="true">A</span>
          <span>AI Data Analyst <small>&amp; Decision Assistant</small></span>
        </a>
        <button ref={menuButtonRef} className="mobile-menu-toggle" type="button" aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"} aria-expanded={menuOpen} aria-controls="public-navigation" onClick={() => setMenuOpen((open) => !open)}>
          <span /><span /><span />
        </button>
        <nav id="public-navigation" className={`public-navigation${menuOpen ? " is-open" : ""}`} aria-label="Main navigation">
          {[ ["Home", "home"], ["Features", "features"], ["How it works", "how-it-works"], ["About", "about"], ["FAQ", "faq"] ].map(([label, id]) => (
            <a key={id} href={`#${id}`} aria-current={activeSection === id ? "location" : undefined} onClick={closeMenu}>{label}</a>
          ))}
          <div className="public-nav-actions">
            <ThemeToggle />
            <Link className="login-link" to={isAuthenticated ? "/dashboard" : "/login"} onClick={closeMenu}>{isAuthenticated ? "Workspace" : "Log in"}</Link>
            <Link className="button button-primary button-small" to={accountHref} onClick={closeMenu}>{isAuthenticated ? "Open workspace" : "Get started"}</Link>
          </div>
        </nav>
      </header>

      <main>
        <section className="landing-hero" id="home">
          <div className="hero-copy">
            <p className="eyebrow"><span className="eyebrow-dot" /> DATA ANALYSIS, MADE DECISIVE</p>
            <h1>Turn Your Data Into <em>Intelligent Decisions</em></h1>
            <p className="hero-description">Upload your CSV or Excel dataset and transform raw data into clear analysis, interactive visualizations, AI-powered insights, recommendations, and professional reports.</p>
            <div className="hero-actions"><Link className="button button-primary" to={accountHref}>Get started <span aria-hidden="true">-&gt;</span></Link><a className="button button-quiet" href="#features">Explore features <span aria-hidden="true">&#8595;</span></a></div>
            <div className="hero-assurance"><span aria-hidden="true">01</span><p>Analysis stays grounded in the statistics and aggregates available for your dataset.</p></div>
          </div>
          <div className="hero-preview-wrap"><div className="preview-orbit preview-orbit-one" /><div className="preview-orbit preview-orbit-two" /><ProductPreview /><div className="preview-caption"><span className="preview-status-dot" /> From dataset to decision support</div></div>
          <a className="hero-scroll-cue" href="#value">Scroll to explore <span aria-hidden="true">&#8595;</span></a>
        </section>

        <section className="value-strip" id="value" aria-label="Platform capabilities">
          <p>ONE WORKSPACE FOR YOUR ANALYSIS</p>
          <div><span>Automated analysis</span><i /> <span>Interactive charts</span><i /> <span>AI insights</span><i /> <span>Professional reports</span></div>
        </section>

        <section className="public-section features-section" id="features">
          <div className="section-intro"><p className="eyebrow">BUILT FOR THE WHOLE WORKFLOW</p><h2>From the first upload to the final recommendation.</h2><p>Keep the analysis, visual exploration, AI assistance, and reporting connected to the same dataset.</p></div>
          <div className="feature-grid">{features.map((feature) => <article className="feature-item" key={feature.title}><span className="feature-mark" aria-hidden="true">{feature.mark}</span><h3>{feature.title}</h3><p>{feature.text}</p></article>)}</div>
        </section>

        <section className="public-section workflow-section" id="how-it-works">
          <div className="section-intro"><p className="eyebrow">A CLEAR PATH THROUGH YOUR DATA</p><h2>Four steps. One connected workspace.</h2><p>Start with the file you have. Use the analysis to decide what to inspect next.</p></div>
          <ol className="workflow-list">{steps.map((step, index) => <li key={step}><span>{String(index + 1).padStart(2, "0")}</span><strong>{step}</strong>{index < steps.length - 1 && <i aria-hidden="true" />}</li>)}</ol>
          <div className="workflow-outcome"><span>INPUT</span><strong>Your dataset</strong><i aria-hidden="true">-&gt;</i><span>OUTPUT</span><strong>Evidence-led decisions</strong></div>
        </section>

        <section className="public-section preview-section" aria-labelledby="preview-heading">
          <div className="section-intro"><p className="eyebrow">A LOOK INSIDE</p><h2 id="preview-heading">A product preview, not a promise.</h2><p>The sample interface below is illustrative. Your charts and findings are generated from the dataset you upload.</p></div>
          <ProductPreview />
        </section>

        <section className="about-band" id="about">
          <div><p className="eyebrow">WHY THIS WORKSPACE</p><h2>Less time assembling analysis. More time understanding what it means.</h2></div>
          <div><p>Manual analysis often means jumping between spreadsheets, charts, and notes. This workspace brings statistical summaries, interactive views, and AI interpretation together so you can investigate a dataset in context.</p><p>The AI assistant and reports work from the available analysis context. When that evidence is insufficient, the system should say so rather than invent an answer.</p></div>
        </section>

        <section className="public-section faq-section" id="faq">
          <div className="section-intro"><p className="eyebrow">QUESTIONS, ANSWERED</p><h2>Know what to expect.</h2></div>
          <div className="faq-list">{faqs.map(([question, answer]) => <details key={question}><summary>{question}<span aria-hidden="true">+</span></summary><p>{answer}</p></details>)}</div>
        </section>

        <section className="final-cta"><div><p className="eyebrow">YOUR NEXT DECISION STARTS HERE</p><h2>Ready to understand your data?</h2><p>Upload your first dataset and turn raw information into meaningful insights.</p></div><Link className="button button-light" to={accountHref}>{isAuthenticated ? "Open workspace" : "Get started"} <span aria-hidden="true">-&gt;</span></Link></section>
      </main>

      <footer className="public-footer"><div className="footer-main"><div className="footer-brand"><a className="brand-lockup" href="#home"><span className="brand-mark" aria-hidden="true">A</span><span>AI Data Analyst <small>&amp; Decision Assistant</small></span></a><p>Clear analysis and grounded AI support for the data you already have.</p></div><div><h2>Explore</h2><a href="#features">Features</a><a href="#how-it-works">How it works</a><a href="#about">About</a><a href="#faq">FAQ</a></div><div><h2>Account</h2><Link to="/login">Log in</Link><Link to="/register">Register</Link></div></div><div className="footer-legal"><span>&copy; {new Date().getFullYear()} AI Data Analyst &amp; Decision Assistant</span><a href="#home">Back to top</a></div></footer>
    </div>
  );
}