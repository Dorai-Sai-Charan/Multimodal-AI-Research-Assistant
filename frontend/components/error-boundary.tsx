"use client";
import React from "react";

interface State { hasError: boolean; }

export class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  State
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center h-screen">
          <div className="text-center">
            <h2 className="text-xl font-semibold mb-2">Something went wrong</h2>
            <p className="text-muted-foreground mb-4">Try refreshing the page.</p>
            <button onClick={() => this.setState({ hasError: false })} className="px-4 py-2 bg-primary text-primary-foreground rounded">
              Retry
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
