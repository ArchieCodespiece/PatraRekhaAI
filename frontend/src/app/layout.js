
import "./globals.css";
import I18nClientWrapper from "../components/I18nClientWrapper";

export const metadata = {
    title: "PatraRekhaAI - Document Intelligence Suite",
    description:
        "AI-powered document management, PDF chat, and smart scheduling platform.",
};

export default function RootLayout({ children }) {
    return (
        <html lang="en" suppressHydrationWarning>
            <head>
                <script
                    dangerouslySetInnerHTML={{
                        __html: `
                            try {
                                const theme = localStorage.getItem("patrerekha:theme");
                                if (theme === "dark" || (!theme && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
                                    document.documentElement.classList.add("dark");
                                }
                            } catch {}
                        `,
                    }}
                />
            </head>
            <body className="bg-background text-foreground antialiased">
                <I18nClientWrapper>
                    {children}
                </I18nClientWrapper>
            </body>
        </html>
    );
}
