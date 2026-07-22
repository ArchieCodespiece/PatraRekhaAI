import "./globals.css";
import Sidebar from "../components/sidebar";

export const metadata = {
    title: "KMRL AI Knowledge Hub",
};

export default function RootLayout({ children }) {
    return (
        <html lang="en">
            <body
                className="bg-gray-100"
                style={{ fontFamily: "Georgia, serif" }}
            >
                <div className="flex min-h-screen">
                    <Sidebar />

                    <main className="flex-1 p-10">
                        {children}
                    </main>
                </div>
            </body>
        </html>
    );
}