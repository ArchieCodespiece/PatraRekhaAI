"use client";

import React from "react";
import { AlertCircle, RefreshCw } from "lucide-react";

export default class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error("ErrorBoundary caught:", error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="flex min-h-[50vh] items-center justify-center p-8">
                    <div className="flex flex-col items-center gap-4 rounded-2xl border border-destructive/20 bg-destructive/5 p-8 text-center">
                        <AlertCircle size={40} className="text-destructive" />
                        <h2 className="text-lg font-semibold text-foreground">
                            Something went wrong
                        </h2>
                        <p className="max-w-md text-sm text-muted-foreground">
                            {this.state.error?.message ||
                                "An unexpected error occurred. Please try again."}
                        </p>
                        <button
                            type="button"
                            onClick={() => {
                                this.setState({ hasError: false, error: null });
                                window.location.reload();
                            }}
                            className="mt-2 flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                        >
                            <RefreshCw size={14} />
                            Reload page
                        </button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}
