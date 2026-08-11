"use client";

import { createClient } from "@supabase/supabase-js";


/* ==========================================================================
   Environment
   ========================================================================== */

const SUPABASE_URL =
    process.env.NEXT_PUBLIC_SUPABASE_URL;

const SUPABASE_ANON_KEY =
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    "http://127.0.0.1:8001";


if (!SUPABASE_URL) {
    throw new Error(
        "Missing NEXT_PUBLIC_SUPABASE_URL."
    );
}

if (!SUPABASE_ANON_KEY) {
    throw new Error(
        "Missing NEXT_PUBLIC_SUPABASE_ANON_KEY."
    );
}


/* ==========================================================================
   Supabase Client
   ========================================================================== */

export const supabase =
    createClient(
        SUPABASE_URL,
        SUPABASE_ANON_KEY,
        {
            auth: {
                persistSession: true,
                autoRefreshToken: true,
                detectSessionInUrl: true,
            },
        }
    );


/* ==========================================================================
   Local Storage Helpers
   ========================================================================== */

function storageKey(key) {
    return `patrerekha:${key}`;
}


export function getStoredAuthUser() {

    if (
        typeof window === "undefined"
    ) {
        return null;
    }

    try {

        const raw =
            window.localStorage.getItem(
                storageKey("auth_user")
            );

        return raw
            ? JSON.parse(raw)
            : null;

    } catch {

        return null;
    }
}


export function setStoredAuthUser(user) {

    if (
        typeof window === "undefined"
    ) {
        return;
    }

    if (!user) {

        window.localStorage.removeItem(
            storageKey("auth_user")
        );

        return;
    }

    const safeUser = {

        id:
            user.id ||
            "",

        email:
            user.email ||
            "",

        displayName:
            user.displayName ||
            user.user_metadata?.full_name ||
            user.user_metadata?.name ||
            user.email?.split("@")[0] ||
            "Signed in user",

        avatarUrl:
            user.avatarUrl ||
            user.user_metadata?.avatar_url ||
            "",
    };

    window.localStorage.setItem(
        storageKey("auth_user"),
        JSON.stringify(safeUser)
    );
}


export function clearStoredAuthUser() {

    if (
        typeof window === "undefined"
    ) {
        return;
    }

    window.localStorage.removeItem(
        storageKey("auth_user")
    );
}


/* ==========================================================================
   Current Session
   ========================================================================== */

export async function getCurrentSession() {

    const {
        data,
        error,
    } =
        await supabase.auth.getSession();

    if (error) {

        throw new Error(
            error.message ||
            "Unable to load your Supabase session."
        );
    }

    return data?.session || null;
}


/* ==========================================================================
   Current User
   ========================================================================== */

export async function getCurrentUser() {

    const session =
        await getCurrentSession();

    if (!session?.user) {
        return null;
    }

    return session.user;
}


/* ==========================================================================
   Build Frontend User
   ========================================================================== */

function buildSessionUser(user) {

    if (!user) {
        return null;
    }

    const email =
        user.email ||
        user.identities?.[0]?.identity_data?.email ||
        "";

    const displayName =
        user.user_metadata?.full_name ||
        user.user_metadata?.name ||
        email.split("@")[0] ||
        "Signed in user";

    return {

        id:
            user.id,

        email,

        displayName,

        avatarUrl:
            user.user_metadata?.avatar_url ||
            "",
    };
}


/* ==========================================================================
   Gmail Activity Heartbeat
   ========================================================================== */

/*
 * The heartbeat belongs to the authenticated browser session.
 *
 * It must NOT depend on the lifetime of one React component.
 *
 * Lifecycle:
 *
 *     signed in
 *        |
 *        v
 *     heartbeat
 *        |
 *        +---- every 60 seconds
 *        |
 *        +---- focus
 *        |
 *        +---- visibility
 *        |
 *        +---- pageshow
 *        |
 *        +---- online
 *        |
 *        v
 *     backend touch
 *        |
 *        v
 *     is_active = TRUE
 *
 * Therefore an inactive Gmail connection can automatically
 * become active again without another OAuth flow.
 */

let gmailHeartbeatTimer = null;

let gmailActivityListenersAttached = false;

let gmailHeartbeatInFlight = false;

let gmailHeartbeatGeneration = 0;


/* --------------------------------------------------------------------------
   Send Gmail activity
   -------------------------------------------------------------------------- */

async function sendGmailActivity() {

    if (
        typeof window === "undefined"
    ) {
        return;
    }

    /*
     * Prevent overlapping heartbeat requests.
     */
    if (gmailHeartbeatInFlight) {
        return;
    }

    gmailHeartbeatInFlight = true;

    try {

        let session =
            await getCurrentSession();

        if (
            !session?.access_token ||
            !session?.user?.email
        ) {
            return;
        }

        const ownerEmail =
            session.user.email;


        /*
         * First heartbeat attempt.
         */
        let response =
            await fetch(
                `${API_BASE_URL}/gmail/connect/heartbeat?owner_email=${encodeURIComponent(
                    ownerEmail
                )}`,
                {
                    method: "POST",

                    headers: {
                        Authorization:
                            `Bearer ${session.access_token}`,

                        "Content-Type":
                            "application/json",
                    },

                    keepalive: true,
                }
            );


        /*
         * The browser may wake up with an expired access token.
         *
         * Refresh the Supabase session and retry the heartbeat once.
         *
         * This is important because Gmail reactivation depends on
         * the heartbeat reaching FastAPI.
         */
        if (
            response.status === 401
        ) {

            try {

                const {
                    data: refreshedData,
                    error: refreshError,
                } =
                    await supabase.auth.refreshSession();

                if (
                    refreshError ||
                    !refreshedData?.session?.access_token
                ) {

                    console.warn(
                        "Unable to refresh Supabase session for Gmail heartbeat:",
                        refreshError?.message ||
                        "No refreshed session."
                    );

                    return;
                }

                session =
                    refreshedData.session;


                response =
                    await fetch(
                        `${API_BASE_URL}/gmail/connect/heartbeat?owner_email=${encodeURIComponent(
                            ownerEmail
                        )}`,
                        {
                            method: "POST",

                            headers: {
                                Authorization:
                                    `Bearer ${session.access_token}`,

                                "Content-Type":
                                    "application/json",
                            },

                            keepalive: true,
                        }
                    );

            } catch (refreshError) {

                console.warn(
                    "Unable to refresh session for Gmail heartbeat:",
                    refreshError
                );

                return;
            }
        }


        if (!response.ok) {

            let detail = "";

            try {

                const data =
                    await response.json();

                detail =
                    data?.detail ||
                    "";

            } catch {
                // Response may not contain JSON.
            }

            console.warn(
                "Gmail activity heartbeat failed:",
                response.status,
                detail
            );

            return;
        }


        /*
         * At this point the backend heartbeat endpoint has accepted
         * the request.
         *
         * touch_gmail_connection() on the backend changes:
         *
         *     is_active = TRUE
         *     last_seen_at = NOW
         *
         * This is the automatic stale -> active transition.
         */
        console.debug(
            `[GMAIL] Heartbeat sent for ${ownerEmail}`
        );

    } catch (error) {

        console.warn(
            "Unable to send Gmail activity heartbeat:",
            error
        );

    } finally {

        gmailHeartbeatInFlight = false;
    }
}


/* --------------------------------------------------------------------------
   Browser activity
   -------------------------------------------------------------------------- */

function handleBrowserActivity() {

    if (
        typeof document !== "undefined" &&
        document.visibilityState === "hidden"
    ) {
        return;
    }

    /*
     * Do not wait for the next 60-second interval.
     *
     * Returning to the browser should reactivate Gmail immediately.
     */
    sendGmailActivity();
}


/* --------------------------------------------------------------------------
   Attach browser listeners
   -------------------------------------------------------------------------- */

function attachGmailActivityListeners() {

    if (
        typeof window === "undefined" ||
        gmailActivityListenersAttached
    ) {
        return;
    }

    document.addEventListener(
        "visibilitychange",
        handleBrowserActivity
    );

    window.addEventListener(
        "focus",
        handleBrowserActivity
    );

    window.addEventListener(
        "pageshow",
        handleBrowserActivity
    );

    window.addEventListener(
        "online",
        handleBrowserActivity
    );

    gmailActivityListenersAttached = true;
}


/* --------------------------------------------------------------------------
   Detach browser listeners
   -------------------------------------------------------------------------- */

function detachGmailActivityListeners() {

    if (
        typeof window === "undefined" ||
        !gmailActivityListenersAttached
    ) {
        return;
    }

    document.removeEventListener(
        "visibilitychange",
        handleBrowserActivity
    );

    window.removeEventListener(
        "focus",
        handleBrowserActivity
    );

    window.removeEventListener(
        "pageshow",
        handleBrowserActivity
    );

    window.removeEventListener(
        "online",
        handleBrowserActivity
    );

    gmailActivityListenersAttached = false;
}


/* --------------------------------------------------------------------------
   Start Gmail heartbeat
   -------------------------------------------------------------------------- */

export function startGmailActivityHeartbeat() {

    if (
        typeof window === "undefined"
    ) {
        return;
    }


    /*
     * Increase the generation so any previous lifecycle is considered
     * obsolete.
     */
    gmailHeartbeatGeneration += 1;


    /*
     * If another timer already exists, do not create duplicate timers.
     */
    if (
        gmailHeartbeatTimer !== null
    ) {

        attachGmailActivityListeners();

        /*
         * Still send an immediate heartbeat.
         *
         * This is important when the connection was marked inactive
         * while the browser was away.
         */
        sendGmailActivity();

        return;
    }


    attachGmailActivityListeners();


    /*
     * CRITICAL:
     *
     * Send immediately.
     *
     * If the backend previously changed:
     *
     *     is_active = FALSE
     *
     * this request changes it back to TRUE through the heartbeat
     * endpoint.
     */
    sendGmailActivity();


    /*
     * Continue sending every 60 seconds.
     */
    const generation =
        gmailHeartbeatGeneration;

    gmailHeartbeatTimer =
        window.setInterval(
            () => {

                /*
                 * Protect against an old timer firing after a restart.
                 */
                if (
                    generation !==
                    gmailHeartbeatGeneration
                ) {
                    return;
                }

                sendGmailActivity();

            },
            60 * 1000
        );
}


/* --------------------------------------------------------------------------
   Stop Gmail heartbeat
   -------------------------------------------------------------------------- */

export function stopGmailActivityHeartbeat() {

    if (
        typeof window !== "undefined" &&
        gmailHeartbeatTimer !== null
    ) {

        window.clearInterval(
            gmailHeartbeatTimer
        );

        gmailHeartbeatTimer = null;
    }


    gmailHeartbeatGeneration += 1;

    detachGmailActivityListeners();

    gmailHeartbeatInFlight = false;
}


/* ==========================================================================
   Gmail Logout Cleanup
   ========================================================================== */

async function deactivateGmailBeforeLogout() {

    try {

        const session =
            await getCurrentSession();

        if (
            !session?.access_token
        ) {
            return;
        }

        await fetch(
            `${API_BASE_URL}/gmail/connect/deactivate`,
            {
                method: "POST",

                headers: {
                    Authorization:
                        `Bearer ${session.access_token}`,

                    "Content-Type":
                        "application/json",
                },

                keepalive: true,
            }
        );

    } catch (error) {

        console.warn(
            "Unable to deactivate Gmail connection before logout:",
            error
        );
    }
}


/* ==========================================================================
   Google OAuth
   ========================================================================== */

export async function signInWithGoogle() {

    if (
        typeof window === "undefined"
    ) {

        throw new Error(
            "Google sign-in can only be started in the browser."
        );
    }

    const redirectTo =
        `${window.location.origin}/auth`;

    const {
        data,
        error,
    } =
        await supabase.auth.signInWithOAuth({

            provider:
                "google",

            options: {
                redirectTo,
            },
        });

    if (error) {

        throw new Error(
            error.message ||
            "Unable to start Google sign-in."
        );
    }

    return data;
}


/* ==========================================================================
   OAuth Session Compatibility Helper
   ========================================================================== */

export async function exchangeSupabaseSessionFromHash() {

    const session =
        await getCurrentSession();

    if (
        !session?.user
    ) {
        return null;
    }

    const sessionUser =
        buildSessionUser(
            session.user
        );

    setStoredAuthUser(
        sessionUser
    );


    /*
     * Start/restart Gmail activity tracking immediately.
     *
     * This handles browser restoration and OAuth return.
     */
    startGmailActivityHeartbeat();


    if (
        typeof window !== "undefined"
    ) {

        const hash =
            window.location.hash;

        if (hash) {

            window.history.replaceState(
                {},
                document.title,
                window.location.pathname +
                    window.location.search
            );
        }
    }

    return {
        ...sessionUser,
    };
}


/* ==========================================================================
   OAuth URL Compatibility Helper
   ========================================================================== */

export function buildSupabaseOAuthUrl(
    provider = "google"
) {

    if (
        typeof window === "undefined"
    ) {

        throw new Error(
            "OAuth URL can only be created in the browser."
        );
    }

    const redirectTo =
        `${window.location.origin}/auth`;

    const url =
        new URL(
            `${SUPABASE_URL}/auth/v1/authorize`
        );

    url.searchParams.set(
        "provider",
        provider
    );

    url.searchParams.set(
        "redirect_to",
        redirectTo
    );

    return url.toString();
}


/* ==========================================================================
   Sign Out
   ========================================================================== */

export async function signOut() {

    /*
     * Gmail must be deactivated BEFORE destroying the
     * Supabase session because the backend needs the
     * current access token.
     */
    await deactivateGmailBeforeLogout();


    /*
     * Stop the browser heartbeat only for an actual logout.
     *
     * This is NOT called by auth-listener cleanup anymore.
     */
    stopGmailActivityHeartbeat();


    const {
        error,
    } =
        await supabase.auth.signOut();

    if (error) {

        throw new Error(
            error.message ||
            "Unable to sign out."
        );
    }

    clearStoredAuthUser();
}


/* ==========================================================================
   Authentication State Listener
   ========================================================================== */

export function onAuthStateChange(
    callback
) {

    const {
        data: {
            subscription,
        },
    } =
        supabase.auth.onAuthStateChange(
            async (
                event,
                session
            ) => {

                const user =
                    session?.user ||
                    null;

                const sessionUser =
                    buildSessionUser(
                        user
                    );


                if (sessionUser) {

                    setStoredAuthUser(
                        sessionUser
                    );


                    /*
                     * A valid authenticated session exists.
                     *
                     * Start the GLOBAL Gmail heartbeat.
                     *
                     * This will also immediately reactivate a Gmail
                     * connection whose is_active flag became false.
                     */
                    startGmailActivityHeartbeat();

                } else {

                    clearStoredAuthUser();


                    /*
                     * Only stop the heartbeat when there is genuinely
                     * no authenticated session.
                     *
                     * We intentionally do NOT stop it merely because
                     * this particular React auth listener is being
                     * unsubscribed.
                     */
                }


                await callback(
                    event,
                    session,
                    sessionUser
                );
            }
        );


    return () => {

        subscription.unsubscribe();

        /*
         * IMPORTANT:
         *
         * Do NOT call stopGmailActivityHeartbeat() here.
         *
         * React components can mount/unmount or recreate their
         * auth listener while the user is still signed in.
         *
         * Stopping the heartbeat here was one of the things that
         * could make the stale -> active recovery unreliable.
         *
         * signOut() explicitly stops the heartbeat.
         */
    };
}


/* ==========================================================================
   Authenticated FastAPI Request
   ========================================================================== */

export async function authenticatedFetch(
    path,
    options = {}
) {

    const {
        data,
        error,
    } =
        await supabase.auth.getSession();

    if (error) {

        throw new Error(
            error.message ||
            "Unable to load authentication session."
        );
    }

    let session =
        data?.session;


    if (
        !session?.access_token
    ) {

        throw new Error(
            "You are not signed in."
        );
    }


    const buildHeaders = (
        accessToken
    ) => {

        const headers =
            new Headers(
                options.headers || {}
            );

        headers.set(
            "Authorization",
            `Bearer ${accessToken}`
        );


        if (
            options.body &&
            !(
                options.body
                instanceof FormData
            ) &&
            !headers.has(
                "Content-Type"
            )
        ) {

            headers.set(
                "Content-Type",
                "application/json"
            );
        }

        return headers;
    };


    let response =
        await fetch(
            `${API_BASE_URL}${path}`,
            {
                ...options,

                headers:
                    buildHeaders(
                        session.access_token
                    ),
            }
        );


    /*
     * If the access token expired, refresh the Supabase
     * session and retry once.
     */
    if (
        response.status === 401
    ) {

        const {
            data: refreshedData,
            error: refreshError,
        } =
            await supabase.auth.refreshSession();

        if (refreshError) {

            throw new Error(
                refreshError.message ||
                "Your session has expired. Please sign in again."
            );
        }

        session =
            refreshedData?.session;


        if (
            session?.access_token
        ) {

            response =
                await fetch(
                    `${API_BASE_URL}${path}`,
                    {
                        ...options,

                        headers:
                            buildHeaders(
                                session.access_token
                            ),
                    }
                );
        }
    }

    return response;
}


/* ==========================================================================
   Gmail Connection
   ========================================================================== */

export async function buildGmailConnectUrl(
    ownerEmail
) {

    if (!ownerEmail) {

        throw new Error(
            "Missing signed-in email."
        );
    }

    const response =
        await authenticatedFetch(
            `/gmail/connect/start?owner_email=${encodeURIComponent(
                ownerEmail
            )}`
        );

    const data =
        await response.json();

    if (!response.ok) {

        throw new Error(
            data?.detail ||
            "Unable to start Gmail connection."
        );
    }

    return data.authorization_url;
}


export async function fetchGmailConnectionStatus(
    ownerEmail
) {

    if (!ownerEmail) {

        return {
            connected: false,
        };
    }

    const response =
        await authenticatedFetch(
            `/gmail/connect/status?owner_email=${encodeURIComponent(
                ownerEmail
            )}`
        );

    const data =
        await response.json();

    if (!response.ok) {

        throw new Error(
            data?.detail ||
            "Unable to load Gmail connection status."
        );
    }

    return data;
}


export async function disconnectGmailConnection(
    ownerEmail
) {

    if (!ownerEmail) {

        return {
            ok: true,
        };
    }

    const response =
        await authenticatedFetch(
            `/gmail/connect?owner_email=${encodeURIComponent(
                ownerEmail
            )}`,
            {
                method: "DELETE",
            }
        );

    const data =
        await response.json();

    if (!response.ok) {

        throw new Error(
            data?.detail ||
            "Unable to disconnect Gmail."
        );
    }

    return data;
}


export async function disconnectAllGmailConnections() {

    const response =
        await authenticatedFetch(
            "/gmail/connect/reset",
            {
                method: "DELETE",
            }
        );

    const data =
        await response.json();

    if (!response.ok) {

        throw new Error(
            data?.detail ||
            "Unable to reset Gmail connections."
        );
    }

    return data;
}


/* ==========================================================================
   Documents
   ========================================================================== */

export async function uploadDocument(
    formData
) {

    if (
        !(formData instanceof FormData)
    ) {

        throw new Error(
            "uploadDocument expects a FormData object."
        );
    }

    const response =
        await authenticatedFetch(
            "/upload-document",
            {
                method: "POST",
                body: formData,
            }
        );

    const data =
        await response.json();

    if (!response.ok) {

        throw new Error(
            data?.detail ||
            "Unable to upload document."
        );
    }

    return data;
}


export async function fetchDocuments() {

    const response =
        await authenticatedFetch(
            "/get-documents"
        );

    const data =
        await response.json();

    if (!response.ok) {

        throw new Error(
            data?.detail ||
            "Unable to load documents."
        );
    }

    return data;
}


export async function fetchDocument(
    fileId
) {

    if (!fileId) {

        throw new Error(
            "Missing file ID."
        );
    }

    const response =
        await authenticatedFetch(
            `/get-documents/${encodeURIComponent(
                fileId
            )}`
        );

    const data =
        await response.json();

    if (!response.ok) {

        throw new Error(
            data?.detail ||
            "Unable to load document."
        );
    }

    return data;
}


export async function deleteDocument(
    fileId
) {

    if (!fileId) {

        throw new Error(
            "Missing file ID."
        );
    }

    const response =
        await authenticatedFetch(
            `/documents/${encodeURIComponent(
                fileId
            )}`,
            {
                method: "DELETE",
            }
        );

    const data =
        await response.json();

    if (!response.ok) {

        throw new Error(
            data?.detail ||
            "Unable to delete document."
        );
    }

    return data;
}


/* ==========================================================================
   Conversations
   ========================================================================== */

export async function fetchConversations() {

    const response =
        await authenticatedFetch(
            "/conversations"
        );

    const data =
        await response.json();

    if (!response.ok) {

        throw new Error(
            data?.detail ||
            "Unable to load conversations."
        );
    }

    return data;
}


export async function fetchConversation(
    conversationId
) {

    if (!conversationId) {

        throw new Error(
            "Missing conversation ID."
        );
    }

    const response =
        await authenticatedFetch(
            `/conversations/${encodeURIComponent(
                conversationId
            )}`
        );

    const data =
        await response.json();

    if (!response.ok) {

        throw new Error(
            data?.detail ||
            "Unable to load conversation."
        );
    }

    return data;
}


/* ==========================================================================
   Chat
   ========================================================================== */

export async function sendChatMessage(
    payload
) {

    if (
        !payload ||
        typeof payload !== "object"
    ) {

        throw new Error(
            "Chat payload is required."
        );
    }

    const response =
        await authenticatedFetch(
            "/chat",
            {
                method: "POST",
                body: JSON.stringify(
                    payload
                ),
            }
        );

    const data =
        await response.json();

    if (!response.ok) {

        throw new Error(
            data?.detail ||
            "Unable to send chat message."
        );
    }

    return data;
}