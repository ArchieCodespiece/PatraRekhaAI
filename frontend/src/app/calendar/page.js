import Calendar from "../../components/calendar";
import { Calendar as CalendarIcon } from "lucide-react";

export default function CalendarPage() {
    return (
        <div className="min-h-screen bg-slate-950 text-slate-100 p-8 flex flex-col gap-6">
            {/* Page Header */}
            <div className="flex items-center gap-3 border-b border-slate-800 pb-5">
                <div className="p-2.5 rounded-xl bg-blue-600/10 text-blue-400 border border-blue-500/20">
                    <CalendarIcon size={22} />
                </div>
                <div>
                    <h1 className="text-xl font-bold tracking-tight text-white">Calendar</h1>
                    <p className="text-xs text-slate-400">Manage schedules and view upcoming dates</p>
                </div>
            </div>

            {/* Reusable Component */}
            <Calendar />
        </div>
    );
}