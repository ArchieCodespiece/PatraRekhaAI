"use client";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8001";

function storageKey(key) {
    return `patrerekha:${key}`;
}

export function getStoredAuthUser() {
    if (typeof window === "undefined") return null;

    try {
        const raw = window.localStorage.getItem(storageKey("auth_user"));
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
}

export function setStoredAuthUser(user) {
    if (typeof window === "undefined") return;

    if (!user) {
        window.localStorage.removeItem(storageKey("auth_user"));
        return;
    }

    window.localStorage.setItem(storageKey("auth_user"), JSON.stringify(user));
}

export function clearStoredAuthUser() {
    setStoredAuthUser(null);
}

export async function exchangeSupabaseSessionFromHash() {
    if (typeof window === "undefined" || !SUPABASE_URL) return null;

    const hash = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : "";
    const params = new URLSearchParams(hash);
    const accessToken = params.get("access_token");

    if (!accessToken) return null;

    const response = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
        headers: {
            Authorization: `Bearer ${accessToken}`,
            apikey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "",
        },
    });

    if (!response.ok) {
        throw new Error("Unable to load your Supabase profile.");
    }

    const user = await response.json();
    const email = user?.email || user?.identities?.[0]?.identity_data?.email || "";
    const displayName =
        user?.user_metadata?.full_name ||
        user?.user_metadata?.name ||
        email.split("@")[0] ||
        "Signed in user";

    const sessionUser = {
        id: user?.id || "",
        email,
        displayName,
        avatarUrl: user?.user_metadata?.avatar_url || "",
    };

    setStoredAuthUser(sessionUser);
    window.history.replaceState({}, document.title, window.location.pathname + window.location.search);
    return sessionUser;
}

export function buildSupabaseOAuthUrl(provider = "google") {
    if (!SUPABASE_URL) {
        throw new Error("Missing NEXT_PUBLIC_SUPABASE_URL.");
    }

    const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (!anonKey) {
        throw new Error("Missing NEXT_PUBLIC_SUPABASE_ANON_KEY.");
    }

    const redirectTo = `${window.location.origin}/auth`;
    const url = new URL(`${SUPABASE_URL}/auth/v1/authorize`);

    url.searchParams.set("provider", provider);
    url.searchParams.set("redirect_to", redirectTo);

    return url.toString();
}

export async function buildGmailConnectUrl(ownerEmail) {
    if (!ownerEmail) {
        throw new Error("Missing signed-in email.");
    }

    const response = await fetch(`${API_BASE_URL}/gmail/connect/start?owner_email=${encodeURIComponent(ownerEmail)}`);
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data?.detail || "Unable to start Gmail connection.");
    }

    return data.authorization_url;
}

export async function fetchGmailConnectionStatus(ownerEmail) {
    if (!ownerEmail) return { connected: false };

    const response = await fetch(`${API_BASE_URL}/gmail/connect/status?owner_email=${encodeURIComponent(ownerEmail)}`);
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data?.detail || "Unable to load Gmail connection status.");
    }

    return data;
}

export async function disconnectGmailConnection(ownerEmail) {
    if (!ownerEmail) return { ok: true };

    const response = await fetch(`${API_BASE_URL}/gmail/connect?owner_email=${encodeURIComponent(ownerEmail)}`, {
        method: "DELETE",
    });
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data?.detail || "Unable to disconnect Gmail.");
    }

    return data;
}

export async function disconnectAllGmailConnections() {
    const response = await fetch(`${API_BASE_URL}/gmail/connect/reset`, { method: "DELETE" });
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data?.detail || "Unable to reset Gmail connections.");
    }

    return data;
}
