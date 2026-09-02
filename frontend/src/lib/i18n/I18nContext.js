"use client";

import {
    createContext,
    useContext,
    useState,
    useCallback,
    useEffect,
    useMemo,
} from "react";
import {
    LANGUAGE_CONFIG,
    DEFAULT_LANGUAGE,
    translate as translateFn,
} from "./translations";

const I18nContext = createContext(null);

const STORAGE_KEY = "patrerekha:language";

/**
 * Detect the initial language from localStorage or browser preference.
 */
function detectInitialLanguage() {
    if (typeof window === "undefined") return DEFAULT_LANGUAGE;

    // 1. Persisted user choice
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && LANGUAGE_CONFIG[stored]) {
        return stored;
    }

    // 2. Browser language
    const browserLang = (
        navigator.language ||
        navigator.userLanguage ||
        DEFAULT_LANGUAGE
    ).slice(0, 2).toLowerCase();

    if (LANGUAGE_CONFIG[browserLang]) {
        return browserLang;
    }

    return DEFAULT_LANGUAGE;
}

export function I18nProvider({ children }) {
    const [language, setLanguageState] = useState(DEFAULT_LANGUAGE);
    const [isHydrated, setIsHydrated] = useState(false);

    // Detect language after mount to avoid hydration mismatch
    useEffect(() => {
        setLanguageState(detectInitialLanguage());
        setIsHydrated(true);
    }, []);

    const setLanguage = useCallback((langCode) => {
        if (!LANGUAGE_CONFIG[langCode]) return;
        setLanguageState(langCode);
        if (typeof window !== "undefined") {
            window.localStorage.setItem(STORAGE_KEY, langCode);
            // Dispatch event for non-React listeners
            window.dispatchEvent(new Event("languagechange"));
        }
    }, []);

    const t = useCallback(
        (key, fallback) => {
            const result = translateFn(key, language);
            if (result === key && fallback) return fallback;
            return result;
        },
        [language],
    );

    const isRTL = useMemo(
        () => LANGUAGE_CONFIG[language]?.rtl ?? false,
        [language],
    );

    // Update <html lang> and <html dir> attributes
    useEffect(() => {
        if (typeof document === "undefined") return;
        document.documentElement.lang = language;
        document.documentElement.dir = isRTL ? "rtl" : "ltr";
    }, [language, isRTL]);

    const value = useMemo(
        () => ({
            language,
            setLanguage,
            t,
            isRTL,
            isHydrated,
            languages: LANGUAGE_CONFIG,
        }),
        [language, setLanguage, t, isRTL, isHydrated],
    );

    return (
        <I18nContext.Provider value={value}>
            {children}
        </I18nContext.Provider>
    );
}

export function useI18n() {
    const ctx = useContext(I18nContext);
    if (!ctx) {
        // Return a fallback so the app doesn't crash outside provider
        return {
            language: DEFAULT_LANGUAGE,
            setLanguage: () => {},
            t: (key, fallback) => fallback || key,
            isRTL: false,
            isHydrated: true,
            languages: LANGUAGE_CONFIG,
        };
    }
    return ctx;
}
