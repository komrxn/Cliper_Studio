import { Component, type ErrorInfo, type ReactNode } from "react";

interface State {
  error: Error | null;
}

/** Catches render errors so one bad view can't blank the whole app. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Cliper UI error:", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="grid min-h-screen place-items-center p-6">
        <div className="panel max-w-md p-8 text-center">
          <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-2xl bg-bad/15 text-bad text-xl">
            !
          </div>
          <h1 className="mb-1 text-lg font-semibold">Something broke</h1>
          <p className="mb-5 text-sm text-ink-400">
            The UI hit an unexpected error. Your rendered clips and sources are safe on disk.
          </p>
          <pre className="mb-5 max-h-32 overflow-auto rounded-lg bg-ink-950 p-3 text-left text-[11px] text-ink-400">
            {this.state.error.message}
          </pre>
          <button className="btn-primary w-full" onClick={() => this.setState({ error: null })}>
            Reload view
          </button>
        </div>
      </div>
    );
  }
}
