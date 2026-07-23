"use client";

import { useState } from "react";
import { DayPicker } from "react-day-picker";
import { format, isSameDay } from "date-fns";
import {
    ChevronLeft,
    ChevronRight,
    Plus,
    Clock,
    CheckCircle2,
    Calendar as CalendarIcon,
    AlertCircle,
    Tag,
    Trash2
} from "lucide-react";
import "react-day-picker/style.css";

// Sample events list
const initialEvents = [
    {
        id: "1",
        date: new Date(),
        title: "Project Sync & Standup",
        time: "10:00 AM - 11:00 AM",
        category: "Meeting",
        completed: false
    },
    {
        id: "2",
        date: new Date(),
        title: "Review PatraRekha UI Mockups",
        time: "02:30 PM - 03:30 PM",
        category: "Design",
        completed: true
    },
    {
        id: "3",
        date: new Date(Date.now() + 86400000 * 2), // 2 days later
        title: "Sprint Planning & Backlog Refinement",
        time: "11:00 AM - 12:30 PM",
        category: "Work",
        completed: false
    }
];

export default function Calendar() {
    const [selectedDate, setSelectedDate] = useState(new Date());
    const [events, setEvents] = useState(initialEvents);
    const [isAddingEvent, setIsAddingEvent] = useState(false);
    const [newEventTitle, setNewEventTitle] = useState("");
    const [newEventTime, setNewEventTime] = useState("09:00 AM");
    const [newEventCategory, setNewEventCategory] = useState("Meeting");

    // Filter events for the currently selected date
    const selectedDateEvents = selectedDate
        ? events.filter((evt) => isSameDay(new Date(evt.date), selectedDate))
        : [];

    const toggleEventComplete = (id) => {
        setEvents((prev) =>
            prev.map((evt) =>
                evt.id === id ? { ...evt, completed: !evt.completed } : evt
            )
        );
    };

    const deleteEvent = (id) => {
        setEvents((prev) => prev.filter((evt) => evt.id !== id));
    };

    const handleAddEvent = (e) => {
        e.preventDefault();
        if (!newEventTitle.trim() || !selectedDate) return;
        const newEvt = {
            id: Date.now().toString(),
            date: selectedDate,
            title: newEventTitle.trim(),
            time: newEventTime || "All Day",
            category: newEventCategory,
            completed: false
        };
        setEvents((prev) => [...prev, newEvt]);
        setNewEventTitle("");
        setIsAddingEvent(false);
    };

    return (
        <div className="w-full max-w-7xl mx-auto flex flex-col lg:flex-row gap-8 items-start">
            {/* Left Side: Calendar Component */}
            <div className="w-full lg:w-96 shrink-0 flex flex-col gap-4">
                <div className="w-full rounded-2xl border border-slate-800 bg-slate-900 p-5 shadow-2xl select-none">
                    <DayPicker
                        mode="single"
                        selected={selectedDate}
                        onSelect={setSelectedDate}
                        showOutsideDays
                        captionLayout="dropdown"
                        navLayout="around"
                        startMonth={new Date(1990, 0)}
                        endMonth={new Date(2100, 11)}
                        classNames={{
                            months: "flex flex-col gap-4",
                            month: "w-full",
                            month_caption: "flex items-center justify-center mb-4 px-2 relative h-10",
                            caption_label: "hidden",
                            dropdowns: "flex items-center gap-2 z-10",
                            dropdown_root: "relative flex items-center bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1 text-sm font-medium text-slate-200 hover:border-slate-600 transition",
                            dropdown: "bg-slate-800 text-slate-100 font-semibold cursor-pointer border-none outline-none",
                            nav: "flex items-center",
                            button_previous: "absolute left-0 top-1 flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800 text-slate-300 transition hover:bg-slate-700 hover:text-white z-20 shadow-sm",
                            button_next: "absolute right-0 top-1 flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800 text-slate-300 transition hover:bg-slate-700 hover:text-white z-20 shadow-sm",
                            month_grid: "w-full border-collapse mx-auto",
                            weekdays: "flex justify-between border-b border-slate-800/80 pb-2 mb-1",
                            weekday: "w-10 text-center text-xs font-semibold uppercase text-slate-500",
                            week: "mt-1 flex justify-between",
                            day: "relative h-10 w-10 text-center p-0",
                            day_button: "flex h-10 w-10 items-center justify-center rounded-lg text-sm text-slate-300 transition hover:bg-slate-800 hover:text-white",
                            selected: "bg-blue-600 text-white hover:bg-blue-500 rounded-lg font-semibold shadow-lg shadow-blue-950/50",
                            today: "border border-blue-500/60 bg-slate-800/80 font-bold text-blue-400 rounded-lg",
                            outside: "text-slate-600 opacity-40",
                            disabled: "text-slate-700 opacity-20",
                        }}
                        components={{
                            Chevron: ({ orientation }) => {
                                if (orientation === "left") {
                                    return <ChevronLeft size={16} />;
                                }
                                return <ChevronRight size={16} />;
                            }
                        }}
                    />

                    <div className="mt-4 flex items-center justify-between border-t border-slate-800/80 pt-4 text-xs">
                        <span className="text-slate-400">Selected Date:</span>
                        <span className="rounded-md bg-blue-950/80 border border-blue-800/40 px-3 py-1 font-medium text-blue-400">
                            {selectedDate ? format(selectedDate, "PPP") : "None"}
                        </span>
                    </div>
                </div>
            </div>

            {/* Right Side: Scheduled Events & Action List */}
            <div className="flex-1 w-full rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl flex flex-col gap-6 min-h-[480px]">
                {/* Events Header */}
                <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-5">
                    <div>
                        <div className="flex items-center gap-2">
                            <CalendarIcon className="text-blue-400" size={20} />
                            <h2 className="text-lg font-bold text-white tracking-tight">
                                {selectedDate ? format(selectedDate, "EEEE, MMMM d, yyyy") : "Select a Date"}
                            </h2>
                        </div>
                        <p className="text-xs text-slate-400 mt-1">
                            {selectedDateEvents.length} {selectedDateEvents.length === 1 ? "event" : "events"} scheduled for this date
                        </p>
                    </div>
                    <button
                        onClick={() => setIsAddingEvent(!isAddingEvent)}
                        className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition shadow-md shadow-blue-950/40 active:scale-95"
                    >
                        <Plus size={16} />
                        {isAddingEvent ? "Cancel" : "Add Event"}
                    </button>
                </div>

                {/* Inline Add Event Form */}
                {isAddingEvent && (
                    <form onSubmit={handleAddEvent} className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
                        <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">New Action / Event</h3>
                        <div className="flex flex-col sm:flex-row gap-3">
                            <input
                                type="text"
                                placeholder="Event title..."
                                value={newEventTitle}
                                onChange={(e) => setNewEventTitle(e.target.value)}
                                className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                                required
                            />
                            <input
                                type="text"
                                placeholder="Time (e.g. 10:00 AM)"
                                value={newEventTime}
                                onChange={(e) => setNewEventTime(e.target.value)}
                                className="w-full sm:w-36 bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                            />
                            <select
                                value={newEventCategory}
                                onChange={(e) => setNewEventCategory(e.target.value)}
                                className="w-full sm:w-32 bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500"
                            >
                                <option value="Meeting">Meeting</option>
                                <option value="Work">Work</option>
                                <option value="Design">Design</option>
                                <option value="Personal">Personal</option>
                            </select>
                        </div>
                        <div className="flex justify-end gap-2 mt-1">
                            <button
                                type="button"
                                onClick={() => setIsAddingEvent(false)}
                                className="px-3 py-1.5 rounded-lg border border-slate-800 text-slate-400 hover:text-slate-200 text-xs transition"
                            >
                                Cancel
                            </button>
                            <button
                                type="submit"
                                className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition"
                            >
                                Save Event
                            </button>
                        </div>
                    </form>
                )}

                {/* Event List */}
                <div className="flex-1 flex flex-col gap-3">
                    {selectedDateEvents.length > 0 ? (
                        selectedDateEvents.map((evt) => (
                            <div
                                key={evt.id}
                                className={`group flex items-center justify-between gap-4 p-4 rounded-xl border transition-all ${
                                    evt.completed
                                        ? "bg-slate-950/60 border-slate-800/60 opacity-60"
                                        : "bg-slate-950 border-slate-800 hover:border-slate-700 shadow-sm"
                                }`}
                            >
                                <div className="flex items-center gap-3.5 min-w-0">
                                    <button
                                        onClick={() => toggleEventComplete(evt.id)}
                                        className={`shrink-0 transition ${
                                            evt.completed ? "text-green-400" : "text-slate-600 hover:text-slate-400"
                                        }`}
                                    >
                                        <CheckCircle2 size={20} />
                                    </button>
                                    <div className="min-w-0">
                                        <h4 className={`text-sm font-semibold truncate ${
                                            evt.completed ? "line-through text-slate-400" : "text-slate-100"
                                        }`}>
                                            {evt.title}
                                        </h4>
                                        <div className="flex items-center gap-3 mt-1 text-xs text-slate-400">
                                            <span className="flex items-center gap-1">
                                                <Clock size={12} className="text-slate-500" />
                                                {evt.time}
                                            </span>
                                            <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[11px]">
                                                <Tag size={10} className="text-blue-400" />
                                                {evt.category}
                                            </span>
                                        </div>
                                    </div>
                                </div>

                                <button
                                    onClick={() => deleteEvent(evt.id)}
                                    className="opacity-0 group-hover:opacity-100 p-2 text-slate-500 hover:text-red-400 transition rounded-lg hover:bg-slate-800"
                                    title="Delete event"
                                >
                                    <Trash2 size={16} />
                                </button>
                            </div>
                        ))
                    ) : (
                        <div className="flex-1 flex flex-col items-center justify-center p-8 border border-dashed border-slate-800 rounded-xl text-center">
                            <div className="p-3 rounded-full bg-slate-800/50 text-slate-500 mb-3">
                                <AlertCircle size={24} />
                            </div>
                            <p className="text-sm font-medium text-slate-300">No events for this date</p>
                            <p className="text-xs text-slate-500 mt-1 max-w-xs">
                                There are no scheduled events or actions for {selectedDate ? format(selectedDate, "MMM d") : "this date"}.
                            </p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}