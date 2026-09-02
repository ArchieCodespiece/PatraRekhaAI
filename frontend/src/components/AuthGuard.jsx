"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getCurrentSession } from "../lib/supabaseAuth";

export default function AuthGuard({ children }) {
    const router = useRouter();
    const [authorized, setAuthorized] = useState(false);
    const [checking, setChecking] = useState(true);

    useEffect(() => {
        let mounted = true;

        async function checkAuth() {
            try {
                const session = await getCurrentSession();

                if (!mounted) return;

                if (session?.access_token) {
                    setAuthorized(true);
                } else {
                    router.replace("/");
                }
            } catch {
                if (mounted) {
                    router.replace("/");
                }
            } finally {
                if (mounted) {
                    setChecking(false);
                }
            }
        }

        checkAuth();

        return () => {
            mounted = false;
        };
    }, [router]);

    if (checking) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-background">
                <div className="flex flex-col items-center gap-4">
                    <div className="h-10 w-10 animate-spin rounded-full border-4 border-border border-t-primary" />
                    <p className="text-sm text-muted-foreground">
                        Verifying session...
                    </p>
                </div>
            </div>
        );
    }

    if (!authorized) {
        return null;
    }

    return children;
}
