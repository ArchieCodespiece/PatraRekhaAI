import "./globals.css";

export const metadata = {
    title: "PatraRekhaAI - Document Intelligence Suite",
    description: "AI-powered document management, PDF chat, and smart scheduling platform.",
};

export default function RootLayout({ children }) {
    return (
        <html lang="en">
            <body className="bg-background text-foreground antialiased">
                {children}
            </body>
        </html>
    );
}