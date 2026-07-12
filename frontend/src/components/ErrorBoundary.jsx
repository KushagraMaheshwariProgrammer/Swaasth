import React from "react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Unhandled render error:", error, info);
  }

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    window.location.assign("/");
  };

  render() {
    const { error } = this.state;
    if (!error) {
      return this.props.children;
    }

    const showDetail = import.meta.env.DEV;

    return (
      <div className="error-boundary">
        <div className="error-boundary-card">
          <h1>Something went wrong</h1>
          <p>
            The app hit an unexpected error. You can reload or return to the home
            screen.
          </p>
          <div className="error-boundary-actions">
            <button type="button" className="analyze-btn" onClick={this.handleReload}>
              Reload
            </button>
            <button
              type="button"
              className="bill-editor-secondary"
              onClick={this.handleGoHome}
            >
              Go home
            </button>
          </div>
          {showDetail && (
            <pre className="error-boundary-detail">{error.stack || error.message}</pre>
          )}
        </div>
      </div>
    );
  }
}
