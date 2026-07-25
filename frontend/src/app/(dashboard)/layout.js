import Sidebar from "../../components/sidebar";

export default function DashboardLayout({ children }) {
    return (
        <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 overflow-auto">
                {children}
            </main>
        </div>
    );
}
