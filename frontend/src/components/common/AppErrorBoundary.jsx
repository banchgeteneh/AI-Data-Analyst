import { Component } from "react";

export default class AppErrorBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <main className="not-found-page" role="alert">
          <p className="eyebrow">TEMPORARY ISSUE</p>
          <h1>We couldn't load this view.</h1>
          <p>Please reload the application. Your account data has not been changed by this screen.</p>
          <button className="button button-primary" type="button" onClick={() => window.location.reload()}>Reload application</button>
          <a className="error-home-link" href="/">Return to home</a>
        </main>
      );
    }

    return this.props.children;
  }
}