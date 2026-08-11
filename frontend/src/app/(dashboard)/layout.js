
"use client";

import { useEffect } from "react";
import Sidebar from "../../components/sidebar";
import {
    getCurrentSession,
    startGmailActivityHeartbeat,
} from "../../lib/supabaseAuth";

export default function DashboardLayout({ children }) {
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

            /*
             * IMPORTANT:
             *
             * Do NOT stop the Gmail heartbeat here.
             *
             * Dashboard navigation can cause components/layouts
             * to mount and unmount. The Gmail heartbeat must remain
             * alive for the authenticated browser session.
             *
             * signOut() in supabaseAuth.js is responsible for
             * stopping the heartbeat.
             */
        };
    }, []);

    return (
        <div className="flex min-h-screen">
            <Sidebar />

            <main className="flex-1 overflow-auto">
                {children}
            </main>
        </div>
    );
}
