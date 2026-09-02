"use client";

import { useState, useRef, useEffect } from "react";
import { Globe, Check, ChevronDown } from "lucide-react";
import { useI18n } from "../lib/i18n/I18nContext";
import { LANGUAGE_CONFIG } from "../lib/i18n/translations";

export default function LanguageSelector() {
    const { language, setLanguage, t, isRTL } = useI18n();
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        function handleClickOutside(event) {
            if (
                containerRef.current &&
                !containerRef.current.contains(event.target)
            ) {
                setIsOpen(false);
            }
        }
        if (isOpen) {
            document.addEventListener("mousedown", handleClickOutside);
            return () =>
                document.removeEventListener("mousedown", handleClickOutside);
        }
    }, [isOpen]);

    const currentLang = LANGUAGE_CONFIG[language];
    const languageList = Object.values(LANGUAGE_CONFIG);

    return (
        <div ref={containerRef} className="relative">
            <button
                type="button"
                onClick={() => setIsOpen((prev) => !prev)}
                className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-white/10 ${
                    isRTL ? "flex-row-reverse" : ""
                }`}
                title={t("lang.selectLanguage")}
                aria-label={t("lang.selectLanguage")}
                aria-expanded={isOpen}
            >
                <Globe size={14} />
                <span className="hidden sm:inline">
                    {currentLang?.nativeName || currentLang?.name || language}
                </span>
                <ChevronDown
                    size={12}
                    className={`transition-transform ${isOpen ? "rotate-180" : ""}`}
                />
            </button>

            {isOpen && (
                <div
                    className={`absolute top-full z-50 mt-1 overflow-hidden rounded-xl border border-sidebar-border bg-popover shadow-xl ${
                        isRTL ? "left-0" : "right-0"
                    }`}
                    style={{ minWidth: "180px" }}
                    role="listbox"
                >
                    <div className="max-h-80 overflow-y-auto py-1">
                        {languageList.map((lang) => {
                            const isActive = lang.code === language;
                            return (
                                <button
                                    key={lang.code}
                                    type="button"
                                    role="option"
                                    aria-selected={isActive}
                                    onClick={() => {
                                        setLanguage(lang.code);
                                        setIsOpen(false);
                                    }}
                                    className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-sm transition-colors ${
                                        isActive
                                            ? "bg-sidebar-primary text-sidebar-primary-foreground"
                                            : "text-popover-foreground hover:bg-accent/10"
                                    } ${lang.rtl ? "flex-row-reverse" : ""}`}
                                >
                                    <div className="flex flex-col items-start gap-0">
                                        <span className="font-medium leading-tight">
                                            {lang.nativeName}
                                        </span>
                                        <span
                                            className={`text-[10px] leading-tight ${
                                                isActive
                                                    ? "text-sidebar-primary-foreground/70"
                                                    : "text-muted-foreground"
                                            }`}
                                        >
                                            {lang.name}
                                        </span>
                                    </div>
                                    {isActive && <Check size={14} />}
                                </button>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}
