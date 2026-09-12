
"use client";

import { useEffect, useState } from "react";
import Sidebar from "../../components/sidebar";
import AuthGuard from "../../components/AuthGuard";
import ErrorBoundary from "../../components/ErrorBoundary";
import {
    getCurrentSession,
    startGmailActivityHeartbeat,
} from "../../lib/supabaseAuth";

export default function DashboardLayout({ children }) {
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

    useEffect(() => {
        let mounted = true;

        async function initializeGmailHeartbeat() {
            try {
                const session = await getCurrentSession();

                if (!mounted) {
                    return;
                }

                if (session?.access_token && session?.user?.email) {
                    startGmailActivityHeartbeat();
                }
            } catch (error) {
                console.warn(
                    "Unable to initialize Gmail activity heartbeat:",
                    error
                );
            }
        }

        initializeGmailHeartbeat();

        return () => {
            mounted = false;
        };
    }, []);

    return (
        <AuthGuard>
            <ErrorBoundary>
                <div className="flex h-screen overflow-hidden bg-background">
                    <Sidebar
                        collapsed={sidebarCollapsed}
                        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
                    />

                    <main className="flex-1 overflow-auto pt-14 lg:pt-0">
                        {children}
                    </main>
                </div>
            </ErrorBoundary>
        </AuthGuard>
    );
}
