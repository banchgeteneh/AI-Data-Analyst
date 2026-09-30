import { Link } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";

export default function NotFoundPage() {
  const { isAuthenticated } = useAuth();

  return (
    <main className="not-found-page">
      <p className="eyebrow">404 / PAGE NOT FOUND</p>
      <h1>This page isn't in your workspace.</h1>
      <p>The address may be incorrect or the page may have moved.</p>
      <Link className="button button-primary" to={isAuthenticated ? "/dashboard" : "/"}>{isAuthenticated ? "Back to dashboard" : "Back to home"}</Link>
    </main>
  );
}