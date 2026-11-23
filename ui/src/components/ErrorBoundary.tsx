import { Component, type ReactNode } from "react";
import { Banner, Button } from "pnd-lib-react";

interface Props {
  /** What failed, for the message, e.g. "Bounties". */
  area: string;
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Keeps a rendering error in one tab from blanking the whole window. Agent data
 * can be oddly shaped; the operator sees what broke and can retry or switch tabs.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack?: string | null }) {
    console.error(`[${this.props.area}] render error`, error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="error-boundary">
        <Banner>
          {this.props.area} hit an error and couldn't be shown: {this.state.error.message}
        </Banner>
        <Button variant="ghost" onClick={() => this.setState({ error: null })}>
          Try again
        </Button>
      </div>
    );
  }
}
