import React, { Component, ErrorInfo, ReactNode } from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Annotator UI error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            padding: '2rem',
            color: '#ef4444',
            background: '#0f172a',
            height: '100vh',
            fontFamily: 'monospace',
            boxSizing: 'border-box',
          }}
        >
          <h2 style={{ color: '#f87171' }}>UI Render Error</h2>
          <pre style={{ whiteSpace: 'pre-wrap', color: '#fca5a5' }}>
            {this.state.error?.toString()}
          </pre>
          <pre style={{ whiteSpace: 'pre-wrap', color: '#94a3b8', fontSize: '12px' }}>
            {this.state.error?.stack}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
