import "./globals.css";
import Sidebar from "../components/sidebar";

export const metadata = {
    title: "PatraRekhaAI – Document Intelligence Suite",
    description: "AI-powered document management, PDF chat, and smart scheduling platform.",
};

export default function RootLayout({ children }) {
    return (
        <html lang="en">
            <body className="bg-background text-foreground antialiased">
                <div className="flex min-h-screen">
                    <Sidebar />
                    <main className="flex-1 overflow-auto">
                        {children}
                    </main>
                </div>
            </body>
        </html>
    );
}