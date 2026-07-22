"use client";

import { useState } from "react";
import { DayPicker } from "react-day-picker";
import { format } from "date-fns";
import { ChevronLeft, ChevronRight } from "lucide-react";
import "react-day-picker/dist/style.css";

export default function Calendar() {
    const [selectedDate, setSelectedDate] = useState(new Date());

    return (
        <div className="flex h-full w-full items-center justify-center bg-slate-950">
            <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-5 shadow-2xl select-none">
                <DayPicker
                    mode="single"
                    selected={selectedDate}
                    onSelect={setSelectedDate}
                    showOutsideDays
                    classNames={{
                        months: "flex",
                        month: "w-full",
                        caption:
                            "flex items-center justify-between mb-4 px-2",
                        caption_label:
                            "text-base font-semibold text-slate-200",
                        nav: "flex gap-2",
                        nav_button:
                            "flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800 text-slate-300 transition hover:bg-slate-700",
                        table: "w-full border-collapse",
                        head_row: "flex",
                        head_cell:
                            "w-10 text-center text-xs font-semibold uppercase text-slate-500",
                        row: "mt-1 flex",
                        cell: "relative h-10 w-10 text-center",
                        day: "flex h-10 w-10 items-center justify-center rounded-lg text-sm text-slate-300 transition hover:bg-slate-800 hover:text-white",
                        day_selected:
                            "bg-blue-600 text-white hover:bg-blue-500",
                        day_today:
                            "border border-blue-500 bg-slate-800 font-bold text-blue-400",
                        day_outside: "text-slate-600",
                        day_disabled: "text-slate-700",
                    }}
                    components={{
                        IconLeft: () => <ChevronLeft size={16} />,
                        IconRight: () => <ChevronRight size={16} />,
                    }}
                />

                <div className="mt-4 flex items-center justify-between border-t border-slate-800 pt-4 text-sm">
                    <span className="text-slate-400">
                        Selected Date
                    </span>

                    <span className="rounded-md bg-blue-950 px-3 py-1 font-medium text-blue-400">
                        {selectedDate
                            ? format(selectedDate, "PPP")
                            : "None"}
                    </span>
                </div>
            </div>
        </div>
    );
}