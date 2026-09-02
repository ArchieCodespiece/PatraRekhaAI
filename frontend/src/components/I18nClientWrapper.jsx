"use client";

import { I18nProvider } from "../lib/i18n/I18nContext";

export default function I18nClientWrapper({ children }) {
    return <I18nProvider>{children}</I18nProvider>;
}
