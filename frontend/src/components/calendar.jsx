
"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { DayPicker } from "react-day-picker";
import {
    addDays,
    format,
    isSameDay,
    isToday,
    startOfWeek,
} from "date-fns";
import {
    AlertCircle,
    AlertTriangle,
    BarChart3,
    Calendar as CalendarIcon,
    CalendarDays,
    CheckCircle2,
    ChevronLeft,
    ChevronRight,
    Clock,
    Flame,
    Info,
    Loader2,
    Plus,
    Sparkles,
    Trash2,
    X,
} from "lucide-react";

import { authenticatedFetch } from "../lib/supabaseAuth";

import "react-day-picker/style.css";

/* -------------------------------------------------------------------------- */
/* Constants                                                                  */
/* -------------------------------------------------------------------------- */

const ACCENT = "#CA8A78";
const ACCENT_HOVER = "#B87A68";

const TEXT_PRIMARY = "#413632";
const TEXT_SECONDARY = "#6B5B54";
const TEXT_MUTED = "#9A8A82";

const BORDER = "#CABDB2";
const BG_BODY = "#FFFBF0";

const MONTH_LABELS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
];

const PRIORITY_KEYS = ["high", "medium", "normal"];

const PRIORITY_CONFIG = {
    high: {
        label: "High",
        color: "bg-[#EF4444]",
        textColor: "text-[#DC2626]",
        dotClass: "bg-[#EF4444]",
        icon: Flame,
    },
    medium: {
        label: "Med",
        color: "bg-[#F59E0B]",
        textColor: "text-[#D97706]",
        dotClass: "bg-[#F59E0B]",
        icon: AlertTriangle,
    },
    normal: {
        label: "Low",
        color: "bg-[#3B82F6]",
        textColor: "text-[#2563EB]",
        dotClass: "bg-[#3B82F6]",
        icon: Info,
    },
};

/* -------------------------------------------------------------------------- */
/* Helpers                                                                    */
/* -------------------------------------------------------------------------- */

function parseApiDate(value) {
    if (!value) {
        return new Date();
    }

    if (value instanceof Date) {
        return value;
    }

    const [year, month, day] = String(value)
        .split("-")
        .map(Number);

    if (year && month && day) {
        return new Date(year, month - 1, day);
    }

    return new Date(value);
}

function normalizeApiEvent(event) {
    return {
        id: event.id,
        date: parseApiDate(event.date),
        title: event.title || "Important date",
        time: event.time || "All Day",
        category: event.category || "Document",
        priority: PRIORITY_CONFIG[event.priority]
            ? event.priority
            : "normal",
        completed: Boolean(event.completed),
        fileHeading: event.file_heading || null,
    };
}

/* -------------------------------------------------------------------------- */
/* Calendar API                                                               */
/* -------------------------------------------------------------------------- */

/*
 * IMPORTANT:
 *
 * Do NOT send owner_email anymore.
 *
 * authenticatedFetch() automatically sends:
 *
 * Authorization: Bearer <supabase_access_token>
 *
 * The FastAPI backend uses that JWT to identify the user.
 */
async function fetchCalendarEvents() {
    const response = await authenticatedFetch(
        "/calender-events"
    );

    const data = await response.json();

    if (!response.ok) {
        throw new Error(
            data?.detail ||
                "Unable to load calendar events."
        );
    }

    return Array.isArray(data?.events)
        ? data.events.map(normalizeApiEvent)
        : [];
}

/* -------------------------------------------------------------------------- */
/* Priority helpers                                                           */
/* -------------------------------------------------------------------------- */

function priorityHex(key) {
    const color =
        PRIORITY_CONFIG[key]?.color || "";

    return (
        color.match(/#[0-9A-Fa-f]{3,8}/)?.[0] ||
        "#94a3b8"
    );
}

function getAvailableYears(events) {
    const years = new Set(
        events.map((event) =>
            event.date.getFullYear()
        )
    );

    years.add(new Date().getFullYear());

    return [...years].sort(
        (a, b) => a - b
    );
}

function getDaysInMonth(year, month) {
    return new Date(
        year,
        month + 1,
        0
    ).getDate();
}

function buildPrioritySeries(
    events,
    year,
    month
) {
    const byPriority = {
        high: [],
        medium: [],
        normal: [],
    };

    if (month === "all") {
        for (let currentMonth = 0; currentMonth < 12; currentMonth++) {
            const monthEvents = events.filter(
                (event) =>
                    event.date.getFullYear() === year &&
                    event.date.getMonth() === currentMonth
            );

            PRIORITY_KEYS.forEach((priority) => {
                byPriority[priority].push(
                    monthEvents.filter(
                        (event) =>
                            event.priority === priority
                    ).length
                );
            });
        }

        return {
            byPriority,
            xLabels: MONTH_LABELS,
        };
    }

    const dayCount = getDaysInMonth(
        year,
        month
    );

    const xLabels = Array.from(
        { length: dayCount },
        (_, index) => String(index + 1)
    );

    for (let day = 1; day <= dayCount; day++) {
        const dayEvents = events.filter(
            (event) =>
                event.date.getFullYear() === year &&
                event.date.getMonth() === month &&
                event.date.getDate() === day
        );

        PRIORITY_KEYS.forEach((priority) => {
            byPriority[priority].push(
                dayEvents.filter(
                    (event) =>
                        event.priority === priority
                ).length
            );
        });
    }

    return {
        byPriority,
        xLabels,
    };
}

/* -------------------------------------------------------------------------- */
/* Priority Chart                                                             */
/* -------------------------------------------------------------------------- */

function PriorityLineChart({ events }) {
    const availableYears = useMemo(
        () => getAvailableYears(events),
        [events]
    );

    const [year, setYear] = useState(
        new Date().getFullYear()
    );

    const [month, setMonth] = useState("all");
    const [hoverIndex, setHoverIndex] = useState(null);

    const containerRef = useRef(null);

    const effectiveYear = availableYears.includes(year)
        ? year
        : availableYears.at(-1) ||
          new Date().getFullYear();

    const { byPriority, xLabels } = useMemo(
        () =>
            buildPrioritySeries(
                events,
                effectiveYear,
                month
            ),
        [events, effectiveYear, month]
    );

    const maxValue = Math.max(
        1,
        ...byPriority.high,
        ...byPriority.medium,
        ...byPriority.normal
    );

    const pad = {
        top: 20,
        right: 16,
        bottom: 28,
        left: 28,
    };

    const svgWidth = 680;
    const svgHeight = 220;

    const innerWidth =
        svgWidth -
        pad.left -
        pad.right;

    const innerHeight =
        svgHeight -
        pad.top -
        pad.bottom;

    const count = xLabels.length;

    const xFor = (index) =>
        pad.left +
        (count <= 1
            ? innerWidth / 2
            : (index * innerWidth) /
              (count - 1));

    const yFor = (value) =>
        pad.top +
        innerHeight -
        (value / maxValue) *
            innerHeight;

    const linePathFor = (values) =>
        values
            .map(
                (value, index) =>
                    `${
                        index === 0
                            ? "M"
                            : "L"
                    }${xFor(index).toFixed(
                        1
                    )},${yFor(
                        value
                    ).toFixed(1)}`
            )
            .join(" ");

    const handleMouseMove = (event) => {
        const rect =
            containerRef.current?.getBoundingClientRect();

        if (!rect || count === 0) {
            return;
        }

        const relativeX =
            ((event.clientX - rect.left) /
                rect.width) *
            svgWidth;

        const step =
            count <= 1
                ? innerWidth
                : innerWidth /
                  (count - 1);

        const index = Math.round(
            (relativeX - pad.left) /
                step
        );

        setHoverIndex(
            Math.max(
                0,
                Math.min(
                    count - 1,
                    index
                )
            )
        );
    };

    const hoverValues =
        hoverIndex !== null
            ? {
                  high:
                      byPriority.high[
                          hoverIndex
                      ] || 0,
                  medium:
                      byPriority.medium[
                          hoverIndex
                      ] || 0,
                  normal:
                      byPriority.normal[
                          hoverIndex
                      ] || 0,
              }
            : null;

    const hoverX =
        hoverIndex !== null
            ? xFor(hoverIndex)
            : 0;

    return (
        <div className="w-full rounded-xl border border-[#CABDB2]/70 bg-white/60 p-4 shadow-lg shadow-[#CA8A78]/8 backdrop-blur-md">
            <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className="rounded-lg border border-[#CA8A78]/20 bg-[#CA8A78]/10 p-1.5">
                        <BarChart3
                            size={16}
                            className="text-[#CA8A78]"
                        />
                    </div>

                    <div>
                        <h3
                            className="text-sm font-bold tracking-tight"
                            style={{
                                color: TEXT_PRIMARY,
                            }}
                        >
                            Priority Analysis
                        </h3>

                        <p
                            className="text-[10px]"
                            style={{
                                color: TEXT_MUTED,
                            }}
                        >
                            {month === "all"
                                ? `Across ${effectiveYear}`
                                : `${MONTH_LABELS[month]} ${effectiveYear}`}
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-1.5">
                    <select
                        value={month}
                        onChange={(event) =>
                            setMonth(
                                event.target.value
                            )
                        }
                        className="cursor-pointer rounded-md border border-[#CABDB2]/60 bg-white/80 px-2 py-1 text-[10px] font-bold outline-none transition hover:border-[#CA8A78]/50"
                        style={{
                            color: TEXT_PRIMARY,
                        }}
                    >
                        <option value="all">
                            All
                        </option>

                        {MONTH_LABELS.map(
                            (
                                label,
                                index
                            ) => (
                                <option
                                    key={label}
                                    value={String(
                                        index
                                    )}
                                >
                                    {label}
                                </option>
                            )
                        )}
                    </select>

                    <select
                        value={effectiveYear}
                        onChange={(event) =>
                            setYear(
                                Number(
                                    event.target
                                        .value
                                )
                            )
                        }
                        className="cursor-pointer rounded-md border border-[#CABDB2]/60 bg-white/80 px-2 py-1 text-[10px] font-bold outline-none transition hover:border-[#CA8A78]/50"
                        style={{
                            color: TEXT_PRIMARY,
                        }}
                    >
                        {availableYears.map(
                            (currentYear) => (
                                <option
                                    key={
                                        currentYear
                                    }
                                    value={
                                        currentYear
                                    }
                                >
                                    {currentYear}
                                </option>
                            )
                        )}
                    </select>
                </div>
            </div>

            <div
                ref={containerRef}
                className="relative w-full overflow-x-auto"
                onMouseMove={handleMouseMove}
                onMouseLeave={() =>
                    setHoverIndex(null)
                }
            >
                <svg
                    viewBox={`0 0 ${svgWidth} ${svgHeight}`}
                    className="min-w-[420px] w-full"
                    style={{
                        height: svgHeight,
                    }}
                    preserveAspectRatio="xMidYMid meet"
                >
                    {Array.from(
                        {
                            length:
                                maxValue + 1,
                        },
                        (_, value) => {
                            const y =
                                yFor(value);

                            return (
                                <g key={value}>
                                    <line
                                        x1={
                                            pad.left
                                        }
                                        x2={
                                            svgWidth -
                                            pad.right
                                        }
                                        y1={y}
                                        y2={y}
                                        stroke={
                                            value ===
                                            0
                                                ? BORDER
                                                : "#E7E5E4"
                                        }
                                        strokeWidth={
                                            1
                                        }
                                        strokeDasharray={
                                            value ===
                                            0
                                                ? "0"
                                                : "2 2"
                                        }
                                    />

                                    <text
                                        x={
                                            pad.left -
                                            6
                                        }
                                        y={y + 3}
                                        textAnchor="end"
                                        fill={
                                            TEXT_MUTED
                                        }
                                        fontSize={
                                            9
                                        }
                                        fontWeight={
                                            600
                                        }
                                    >
                                        {value}
                                    </text>
                                </g>
                            );
                        }
                    )}

                    {xLabels.map(
                        (label, index) => {
                            const x =
                                xFor(
                                    index
                                );

                            const show =
                                count <=
                                    12 ||
                                index %
                                    Math.ceil(
                                        count /
                                            12
                                    ) ===
                                    0 ||
                                index ===
                                    count -
                                        1;

                            if (!show) {
                                return null;
                            }

                            return (
                                <text
                                    key={`${label}-${index}`}
                                    x={x}
                                    y={
                                        svgHeight -
                                        pad.bottom +
                                        14
                                    }
                                    textAnchor="middle"
                                    fill={
                                        TEXT_MUTED
                                    }
                                    fontSize={
                                        9
                                    }
                                    fontWeight={
                                        600
                                    }
                                >
                                    {label}
                                </text>
                            );
                        }
                    )}

                    {hoverIndex !== null && (
                        <line
                            x1={hoverX}
                            x2={hoverX}
                            y1={pad.top}
                            y2={
                                svgHeight -
                                pad.bottom
                            }
                            stroke={ACCENT}
                            strokeWidth={1.5}
                            strokeDasharray="3 2"
                        />
                    )}

                    {PRIORITY_KEYS.map(
                        (priority) => (
                            <path
                                key={priority}
                                d={linePathFor(
                                    byPriority[
                                        priority
                                    ]
                                )}
                                fill="none"
                                stroke={priorityHex(
                                    priority
                                )}
                                strokeWidth={
                                    2.5
                                }
                                strokeLinecap="round"
                                strokeLinejoin="round"
                            />
                        )
                    )}

                    {PRIORITY_KEYS.map(
                        (priority) =>
                            byPriority[
                                priority
                            ].map(
                                (
                                    value,
                                    index
                                ) => (
                                    <circle
                                        key={`${priority}-${index}`}
                                        cx={xFor(
                                            index
                                        )}
                                        cy={yFor(
                                            value
                                        )}
                                        r={
                                            index ===
                                            hoverIndex
                                                ? 4
                                                : 2.5
                                        }
                                        fill="white"
                                        stroke={priorityHex(
                                            priority
                                        )}
                                        strokeWidth={
                                            2
                                        }
                                    />
                                )
                            )
                    )}
                </svg>

                {hoverValues &&
                    hoverIndex !== null && (
                        <div
                            className="pointer-events-none absolute z-20 rounded-lg border border-[#CABDB2]/70 bg-white/95 px-2.5 py-2 shadow-md backdrop-blur-sm"
                            style={{
                                left: `clamp(4px, ${
                                    (hoverX /
                                        svgWidth) *
                                    100
                                }%, calc(100% - 160px))`,
                                top: 4,
                            }}
                        >
                            <p
                                className="mb-1 text-[9px] font-bold uppercase tracking-wider"
                                style={{
                                    color: TEXT_MUTED,
                                }}
                            >
                                {month ===
                                "all"
                                    ? xLabels[
                                          hoverIndex
                                      ]
                                    : `${
                                          xLabels[
                                              hoverIndex
                                          ]
                                      } ${
                                          MONTH_LABELS[
                                              month
                                          ]
                                      }`}
                            </p>

                            {PRIORITY_KEYS.map(
                                (priority) => (
                                    <div
                                        key={
                                            priority
                                        }
                                        className="flex items-center gap-2 py-0.5"
                                    >
                                        <span
                                            className={`h-1.5 w-1.5 rounded-full ${PRIORITY_CONFIG[priority].dotClass}`}
                                        />

                                        <span
                                            className="text-[10px] font-medium"
                                            style={{
                                                color: TEXT_SECONDARY,
                                            }}
                                        >
                                            {
                                                PRIORITY_CONFIG[
                                                    priority
                                                ].label
                                            }
                                        </span>

                                        <span
                                            className="ml-auto pl-3 text-[10px] font-bold tabular-nums"
                                            style={{
                                                color: TEXT_PRIMARY,
                                            }}
                                        >
                                            {
                                                hoverValues[
                                                    priority
                                                ]
                                            }
                                        </span>
                                    </div>
                                )
                            )}
                        </div>
                    )}
            </div>

            <div className="mt-2.5 flex flex-wrap items-center gap-3 border-t border-[#CABDB2]/50 pt-2">
                {PRIORITY_KEYS.map(
                    (priority) => {
                        const config =
                            PRIORITY_CONFIG[
                                priority
                            ];

                        const Icon =
                            config.icon;

                        return (
                            <div
                                key={priority}
                                className="flex items-center gap-1.5"
                            >
                                <Icon
                                    size={11}
                                    className={
                                        config.textColor
                                    }
                                />

                                <span
                                    className="text-[10px] font-bold"
                                    style={{
                                        color: TEXT_SECONDARY,
                                    }}
                                >
                                    {
                                        config.label
                                    }
                                </span>
                            </div>
                        );
                    }
                )}
            </div>
        </div>
    );
}

/* -------------------------------------------------------------------------- */
/* Completion Animation                                                       */
/* -------------------------------------------------------------------------- */

function CompletionBurst({ visible }) {
    if (!visible) {
        return null;
    }

    return (
        <div className="pointer-events-none absolute inset-0 z-10 overflow-hidden rounded-lg">
            <div className="absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 animate-ping rounded-full bg-[#CA8A78]" />
        </div>
    );
}

/* -------------------------------------------------------------------------- */
/* Main Calendar                                                              */
/* -------------------------------------------------------------------------- */

export default function Calendar() {
    const [selectedDate, setSelectedDate] =
        useState(new Date());

    const [events, setEvents] = useState([]);

    const [isEventsLoading, setIsEventsLoading] =
        useState(true);

    const [eventsError, setEventsError] =
        useState("");

    const [isAddingEvent, setIsAddingEvent] =
        useState(false);

    const [newEventTitle, setNewEventTitle] =
        useState("");

    const [newEventTime, setNewEventTime] =
        useState("09:00 AM");

    const [newEventCategory, setNewEventCategory] =
        useState("Meeting");

    const [newEventPriority, setNewEventPriority] =
        useState("normal");

    const [completingId, setCompletingId] =
        useState(null);

    /* ---------------------------------------------------------------------- */
    /* Load events                                                            */
    /* ---------------------------------------------------------------------- */

    useEffect(() => {
        let active = true;

        setIsEventsLoading(true);
        setEventsError("");

        fetchCalendarEvents()
            .then((nextEvents) => {
                if (active) {
                    setEvents(nextEvents);
                }
            })
            .catch((error) => {
                if (active) {
                    setEventsError(
                        error?.message ||
                            "Unable to load calendar events."
                    );
                }
            })
            .finally(() => {
                if (active) {
                    setIsEventsLoading(false);
                }
            });

        return () => {
            active = false;
        };
    }, []);

    /* ---------------------------------------------------------------------- */
    /* Derived data                                                           */
    /* ---------------------------------------------------------------------- */

    const selectedDateEvents = useMemo(
        () =>
            selectedDate
                ? events.filter((event) =>
                      isSameDay(
                          event.date,
                          selectedDate
                      )
                  )
                : [],
        [events, selectedDate]
    );

    const datePriorityMap = useMemo(() => {
        const priorityMap = {};

        const priorityOrder = {
            high: 3,
            medium: 2,
            normal: 1,
        };

        events.forEach((event) => {
            const key = format(
                event.date,
                "yyyy-MM-dd"
            );

            const current =
                priorityMap[key];

            if (
                !current ||
                priorityOrder[event.priority] >
                    priorityOrder[current]
            ) {
                priorityMap[key] =
                    event.priority;
            }
        });

        return priorityMap;
    }, [events]);

    const today = new Date();

    const todayEvents = events.filter(
        (event) =>
            isSameDay(
                event.date,
                today
            )
    );

    const pendingEvents = events.filter(
        (event) => !event.completed
    );

    const completedEvents = events.filter(
        (event) => event.completed
    );

    const overdueEvents = events.filter(
        (event) =>
            !event.completed &&
            event.date <
                new Date(
                    today.getFullYear(),
                    today.getMonth(),
                    today.getDate()
                )
    );

    const weekStart = startOfWeek(
        today,
        {
            weekStartsOn: 1,
        }
    );

    const upcomingWeek = Array.from(
        { length: 7 },
        (_, index) =>
            addDays(
                weekStart,
                index
            )
    );

    const weekEventCounts =
        upcomingWeek.map((date) => ({
            date,
            count: events.filter(
                (event) =>
                    isSameDay(
                        event.date,
                        date
                    )
            ).length,
            isToday: isToday(date),
        }));

    const workloadPercent = Math.min(
        100,
        Math.round(
            (pendingEvents.length /
                Math.max(
                    1,
                    events.length
                )) *
                100
        )
    );

    const busyDays = weekEventCounts.filter(
        (day) => day.count > 0
    ).length;

    const freeSlots = 7 - busyDays;

    /* ---------------------------------------------------------------------- */
    /* Event actions                                                          */
    /* ---------------------------------------------------------------------- */

    const toggleEventComplete = (id) => {
        setEvents((current) =>
            current.map((event) =>
                event.id === id
                    ? {
                          ...event,
                          completed:
                              !event.completed,
                      }
                    : event
            )
        );
    };

    const triggerCompletion = (id) => {
        setCompletingId(id);

        toggleEventComplete(id);

        window.setTimeout(() => {
            setCompletingId(null);
        }, 600);
    };

    const deleteEvent = (id) => {
        setEvents((current) =>
            current.filter(
                (event) =>
                    event.id !== id
            )
        );
    };

    const handleAddEvent = (event) => {
        event.preventDefault();

        if (
            !newEventTitle.trim() ||
            !selectedDate
        ) {
            return;
        }

        const newEvent = {
            id: `local-${Date.now()}`,
            date: selectedDate,
            title: newEventTitle.trim(),
            time:
                newEventTime ||
                "All Day",
            category:
                newEventCategory ||
                "Meeting",
            priority:
                newEventPriority,
            completed: false,
            fileHeading: null,
        };

        setEvents((current) => [
            ...current,
            newEvent,
        ]);

        setNewEventTitle("");
        setNewEventTime("09:00 AM");
        setNewEventCategory("Meeting");
        setNewEventPriority("normal");
        setIsAddingEvent(false);
    };

    /* ---------------------------------------------------------------------- */
    /* Render                                                                 */
    /* ---------------------------------------------------------------------- */

    return (
        <div
            className="flex h-full flex-col gap-3"
            style={{
                backgroundColor: BG_BODY,
            }}
        >
            {/* Stats */}
            <div className="grid grid-cols-4 gap-3">
                {[
                    {
                        label: "Today's Events",
                        value: todayEvents.length,
                        icon: CalendarDays,
                        color: "text-[#CA8A78]",
                    },
                    {
                        label: "Pending",
                        value: pendingEvents.length,
                        icon: Clock,
                        color: "text-[#F59E0B]",
                    },
                    {
                        label: "Completed",
                        value: completedEvents.length,
                        icon: CheckCircle2,
                        color: "text-[#22C55E]",
                    },
                    {
                        label: "Overdue",
                        value: overdueEvents.length,
                        icon: AlertCircle,
                        color: "text-[#EF4444]",
                    },
                ].map((stat) => {
                    const Icon = stat.icon;

                    return (
                        <div
                            key={stat.label}
                            className="flex items-center gap-3 rounded-xl border border-[#CABDB2]/70 bg-white/60 p-3 shadow-md shadow-[#CA8A78]/6 backdrop-blur-md transition-all duration-200 hover:scale-[1.02] hover:border-[#CA8A78]/40"
                        >
                            <div
                                className={`rounded-lg border border-[#CABDB2]/60 bg-white/80 p-2 ${stat.color}`}
                            >
                                <Icon size={16} />
                            </div>

                            <div>
                                <p
                                    className="text-[10px] font-bold uppercase tracking-wider"
                                    style={{
                                        color: TEXT_MUTED,
                                    }}
                                >
                                    {stat.label}
                                </p>

                                <p
                                    className="mt-0.5 text-lg font-bold leading-none"
                                    style={{
                                        color: TEXT_PRIMARY,
                                    }}
                                >
                                    {stat.value}
                                </p>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Main layout */}
            <div className="grid min-h-0 flex-1 grid-cols-[340px_1fr_280px] gap-3">
                {/* ------------------------------------------------------------------ */}
                {/* Left column                                                        */}
                {/* ------------------------------------------------------------------ */}

                <div className="flex min-h-0 flex-col gap-3">
                    {/* Calendar */}
                    <div className="select-none rounded-xl border border-[#CABDB2]/70 bg-white/60 p-3 shadow-md shadow-[#CA8A78]/6 backdrop-blur-md">
                        <DayPicker
                            mode="single"
                            selected={selectedDate}
                            onSelect={(date) =>
                                date &&
                                setSelectedDate(
                                    date
                                )
                            }
                            showOutsideDays
                            captionLayout="dropdown"
                            navLayout="around"
                            startMonth={
                                new Date(
                                    1990,
                                    0
                                )
                            }
                            endMonth={
                                new Date(
                                    2100,
                                    11
                                )
                            }
                            classNames={{
                                months: "flex flex-col gap-2",
                                month: "w-full",
                                month_caption:
                                    "relative mb-2 flex h-8 items-center justify-center px-1",
                                caption_label:
                                    "hidden",
                                dropdowns:
                                    "z-10 flex items-center gap-1.5",
                                dropdown_root:
                                    "relative flex items-center rounded-md border border-[#CABDB2]/60 bg-white/90 px-2 py-0.5 text-xs font-semibold transition hover:border-[#CA8A78]/50",
                                dropdown:
                                    "cursor-pointer border-none bg-white/90 text-xs font-semibold text-[#413632] outline-none",
                                nav: "flex items-center",
                                button_previous:
                                    "absolute left-0 top-0.5 z-20 flex h-6 w-6 items-center justify-center rounded-md border border-[#CABDB2]/60 bg-white/90 text-[#6B5B54] transition hover:border-[#CA8A78]/50 hover:text-[#CA8A78]",
                                button_next:
                                    "absolute right-0 top-0.5 z-20 flex h-6 w-6 items-center justify-center rounded-md border border-[#CABDB2]/60 bg-white/90 text-[#6B5B54] transition hover:border-[#CA8A78]/50 hover:text-[#CA8A78]",
                                month_grid:
                                    "mx-auto w-full border-collapse",
                                weekdays:
                                    "mb-1 flex justify-between border-b border-[#CABDB2]/50 pb-1",
                                weekday:
                                    "w-7 text-center text-[9px] font-bold uppercase tracking-wider",
                                week: "mt-0.5 flex justify-between",
                                day: "relative h-7 w-7 p-0 text-center",
                            }}
                            components={{
                                Chevron: ({
                                    orientation,
                                }) =>
                                    orientation ===
                                    "left" ? (
                                        <ChevronLeft
                                            size={
                                                14
                                            }
                                        />
                                    ) : (
                                        <ChevronRight
                                            size={
                                                14
                                            }
                                        />
                                    ),

                                DayButton: ({
                                    day,
                                    modifiers,
                                    ...props
                                }) => {
                                    const key =
                                        format(
                                            day.date,
                                            "yyyy-MM-dd"
                                        );

                                    const priority =
                                        datePriorityMap[
                                            key
                                        ];

                                    const config =
                                        priority
                                            ? PRIORITY_CONFIG[
                                                  priority
                                              ]
                                            : null;

                                    return (
                                        <div className="relative flex h-7 w-7 items-center justify-center">
                                            <button
                                                {...props}
                                                className={`
                                                    flex h-6 w-6 items-center justify-center rounded-md text-xs font-semibold transition-all duration-150
                                                    ${
                                                        modifiers.selected
                                                            ? "scale-110 bg-[#CA8A78] text-white shadow-sm shadow-[#CA8A78]/25"
                                                            : ""
                                                    }
                                                    ${
                                                        modifiers.today &&
                                                        !modifiers.selected
                                                            ? "border border-[#CA8A78] bg-[#FFFBF0] text-[#CA8A78]"
                                                            : ""
                                                    }
                                                    ${
                                                        modifiers.outside
                                                            ? "text-[#9A8A82] opacity-40"
                                                            : ""
                                                    }
                                                    ${
                                                        !modifiers.selected &&
                                                        !modifiers.today &&
                                                        !modifiers.outside
                                                            ? "text-[#413632] hover:bg-[#FFFBF0]"
                                                            : ""
                                                    }
                                                `}
                                            >
                                                {
                                                    day
                                                        .date
                                                        .getDate()
                                                }
                                            </button>

                                            {config && (
                                                <span
                                                    className={`absolute bottom-0.5 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full ${config.dotClass}`}
                                                />
                                            )}
                                        </div>
                                    );
                                },
                            }}
                        />

                        <div className="mt-2.5 flex items-center justify-between border-t border-[#CABDB2]/50 pt-2">
                            <span
                                className="text-[10px] font-bold uppercase tracking-wider"
                                style={{
                                    color: TEXT_MUTED,
                                }}
                            >
                                Selected
                            </span>

                            <span
                                className="rounded-md border border-[#CABDB2]/60 bg-[#FFFBF0] px-2 py-0.5 text-[10px] font-bold"
                                style={{
                                    color: ACCENT,
                                }}
                            >
                                {selectedDate
                                    ? format(
                                          selectedDate,
                                          "MMM d"
                                      )
                                    : "None"}
                            </span>
                        </div>
                    </div>

                    {/* Priority */}
                    <div className="rounded-xl border border-[#CABDB2]/70 bg-white/60 p-3 shadow-md shadow-[#CA8A78]/6 backdrop-blur-md">
                        <p
                            className="mb-2 text-[9px] font-bold uppercase tracking-wider"
                            style={{
                                color: TEXT_MUTED,
                            }}
                        >
                            Priority
                        </p>

                        <div className="flex flex-wrap gap-1.5">
                            {PRIORITY_KEYS.map(
                                (priority) => {
                                    const config =
                                        PRIORITY_CONFIG[
                                            priority
                                        ];

                                    const count =
                                        events.filter(
                                            (
                                                event
                                            ) =>
                                                event.priority ===
                                                priority
                                        ).length;

                                    return (
                                        <span
                                            key={
                                                priority
                                            }
                                            className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-bold text-white ${config.color}`}
                                        >
                                            {
                                                config.label
                                            }

                                            <span className="opacity-80">
                                                {
                                                    count
                                                }
                                            </span>
                                        </span>
                                    );
                                }
                            )}
                        </div>
                    </div>
                </div>

                {/* ------------------------------------------------------------------ */}
                {/* Center column                                                      */}
                {/* ------------------------------------------------------------------ */}

                <div className="flex min-h-0 flex-col gap-3">
                    <div className="flex min-h-0 flex-1 flex-col rounded-xl border border-[#CABDB2]/70 bg-white/60 p-4 shadow-md shadow-[#CA8A78]/6 backdrop-blur-md">
                        <div className="mb-3 flex items-center justify-between">
                            <div className="flex items-center gap-2.5">
                                <div className="rounded-lg border border-[#CA8A78]/20 bg-[#CA8A78]/10 p-1.5">
                                    <CalendarIcon
                                        size={18}
                                        className="text-[#CA8A78]"
                                    />
                                </div>

                                <div>
                                    <h2
                                        className="text-sm font-bold tracking-tight"
                                        style={{
                                            color: TEXT_PRIMARY,
                                        }}
                                    >
                                        {selectedDate
                                            ? format(
                                                  selectedDate,
                                                  "EEEE, MMMM d"
                                              )
                                            : "Select a Date"}
                                    </h2>

                                    <p
                                        className="text-[10px] font-medium"
                                        style={{
                                            color: TEXT_MUTED,
                                        }}
                                    >
                                        {
                                            selectedDateEvents.length
                                        }{" "}
                                        {selectedDateEvents.length ===
                                        1
                                            ? "event"
                                            : "events"}
                                    </p>
                                </div>
                            </div>

                            <button
                                onClick={() =>
                                    setIsAddingEvent(
                                        (current) =>
                                            !current
                                    )
                                }
                                className="inline-flex items-center gap-1.5 rounded-lg bg-[#CA8A78] px-3 py-1.5 text-[11px] font-bold text-white shadow-md shadow-[#CA8A78]/15 transition-all duration-200 hover:bg-[#B87A68] active:scale-[0.97]"
                            >
                                {isAddingEvent ? (
                                    <X size={14} />
                                ) : (
                                    <Plus size={14} />
                                )}

                                {isAddingEvent
                                    ? "Cancel"
                                    : "Add"}
                            </button>
                        </div>

                        {/* Add event */}
                        {isAddingEvent && (
                            <form
                                onSubmit={
                                    handleAddEvent
                                }
                                className="mb-3 flex flex-col gap-2 rounded-lg border border-[#CABDB2]/60 bg-white/80 p-3"
                            >
                                <input
                                    type="text"
                                    placeholder="Event title..."
                                    value={
                                        newEventTitle
                                    }
                                    onChange={(
                                        event
                                    ) =>
                                        setNewEventTitle(
                                            event
                                                .target
                                                .value
                                        )
                                    }
                                    className="rounded-md border border-[#CABDB2]/60 bg-white/70 px-2.5 py-1.5 text-xs placeholder-[#9A8A82] outline-none transition focus:border-[#CA8A78] focus:ring-1 focus:ring-[#CA8A78]/20"
                                    style={{
                                        color: TEXT_PRIMARY,
                                    }}
                                    required
                                />

                                <div className="flex gap-2">
                                    <input
                                        type="text"
                                        placeholder="Time"
                                        value={
                                            newEventTime
                                        }
                                        onChange={(
                                            event
                                        ) =>
                                            setNewEventTime(
                                                event
                                                    .target
                                                    .value
                                            )
                                        }
                                        className="w-24 rounded-md border border-[#CABDB2]/60 bg-white/70 px-2.5 py-1.5 text-xs outline-none transition focus:border-[#CA8A78]"
                                        style={{
                                            color: TEXT_PRIMARY,
                                        }}
                                    />

                                    <select
                                        value={
                                            newEventPriority
                                        }
                                        onChange={(
                                            event
                                        ) =>
                                            setNewEventPriority(
                                                event
                                                    .target
                                                    .value
                                            )
                                        }
                                        className="flex-1 rounded-md border border-[#CABDB2]/60 bg-white/70 px-2.5 py-1.5 text-xs outline-none transition focus:border-[#CA8A78]"
                                        style={{
                                            color: TEXT_PRIMARY,
                                        }}
                                    >
                                        <option value="high">
                                            High
                                        </option>

                                        <option value="medium">
                                            Medium
                                        </option>

                                        <option value="normal">
                                            Low
                                        </option>
                                    </select>
                                </div>

                                <input
                                    type="text"
                                    placeholder="Category"
                                    value={
                                        newEventCategory
                                    }
                                    onChange={(
                                        event
                                    ) =>
                                        setNewEventCategory(
                                            event
                                                .target
                                                .value
                                        )
                                    }
                                    className="rounded-md border border-[#CABDB2]/60 bg-white/70 px-2.5 py-1.5 text-xs outline-none transition focus:border-[#CA8A78]"
                                    style={{
                                        color: TEXT_PRIMARY,
                                    }}
                                />

                                <div className="mt-0.5 flex justify-end gap-2">
                                    <button
                                        type="button"
                                        onClick={() =>
                                            setIsAddingEvent(
                                                false
                                            )
                                        }
                                        className="rounded-md border border-[#CABDB2]/60 px-3 py-1 text-[10px] font-bold text-[#6B5B54] transition hover:text-[#413632]"
                                    >
                                        Cancel
                                    </button>

                                    <button
                                        type="submit"
                                        className="rounded-md bg-[#CA8A78] px-3 py-1 text-[10px] font-bold text-white shadow-sm transition hover:bg-[#B87A68]"
                                    >
                                        Save
                                    </button>
                                </div>
                            </form>
                        )}

                        {/* Events */}
                        <div className="flex-1 space-y-1.5 overflow-y-auto pr-1 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-[#CABDB2] [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar]:w-1">
                            {isEventsLoading ? (
                                <div className="flex flex-col items-center justify-center py-10">
                                    <Loader2
                                        size={20}
                                        className="mb-2 animate-spin text-[#CA8A78]"
                                    />

                                    <p
                                        className="text-[11px] font-medium"
                                        style={{
                                            color: TEXT_SECONDARY,
                                        }}
                                    >
                                        Loading events...
                                    </p>
                                </div>
                            ) : eventsError ? (
                                <div className="flex flex-col items-center justify-center py-10 text-center">
                                    <AlertCircle
                                        size={20}
                                        className="mb-2 text-[#EF4444]"
                                    />

                                    <p
                                        className="text-[11px] font-medium"
                                        style={{
                                            color: TEXT_PRIMARY,
                                        }}
                                    >
                                        Could not load
                                        events
                                    </p>

                                    <p
                                        className="mt-1 max-w-[280px] text-[9px]"
                                        style={{
                                            color: TEXT_MUTED,
                                        }}
                                    >
                                        {eventsError}
                                    </p>
                                </div>
                            ) : selectedDateEvents.length ===
                              0 ? (
                                <div className="flex flex-col items-center justify-center py-10">
                                    <div className="mb-2 rounded-full border border-[#CABDB2]/50 bg-[#FFFBF0] p-2">
                                        <AlertCircle
                                            size={
                                                20
                                            }
                                            style={{
                                                color: TEXT_MUTED,
                                            }}
                                        />
                                    </div>

                                    <p
                                        className="text-[11px] font-medium"
                                        style={{
                                            color: TEXT_PRIMARY,
                                        }}
                                    >
                                        No events
                                        scheduled
                                    </p>
                                </div>
                            ) : (
                                selectedDateEvents.map(
                                    (event) => {
                                        const config =
                                            PRIORITY_CONFIG[
                                                event.priority
                                            ] ||
                                            PRIORITY_CONFIG.normal;

                                        const isCompleting =
                                            completingId ===
                                            event.id;

                                        return (
                                            <div
                                                key={
                                                    event.id
                                                }
                                                className={`
                                                    group relative flex items-center gap-2.5 rounded-lg border px-2.5 py-2 transition-all duration-300 hover:shadow-sm
                                                    ${
                                                        event.completed
                                                            ? "border-[#FECACA]/50 bg-[#FEF2F2]/50 opacity-60"
                                                            : "border-[#CABDB2]/50 bg-white/70 hover:border-[#CA8A78]/30"
                                                    }
                                                `}
                                            >
                                                <CompletionBurst
                                                    visible={
                                                        isCompleting
                                                    }
                                                />

                                                <button
                                                    onClick={() =>
                                                        triggerCompletion(
                                                            event.id
                                                        )
                                                    }
                                                    className={`
                                                        shrink-0 transition-all duration-300
                                                        ${
                                                            event.completed
                                                                ? "scale-110 text-[#22C55E]"
                                                                : "text-[#CABDB2] hover:scale-110 hover:text-[#CA8A78]"
                                                        }
                                                    `}
                                                    aria-label={
                                                        event.completed
                                                            ? "Mark incomplete"
                                                            : "Mark complete"
                                                    }
                                                >
                                                    <CheckCircle2
                                                        size={
                                                            16
                                                        }
                                                    />
                                                </button>

                                                <div className="min-w-0 flex-1">
                                                    <div className="flex items-center gap-2">
                                                        <span
                                                            className="shrink-0 text-[10px] font-bold tabular-nums"
                                                            style={{
                                                                color: TEXT_MUTED,
                                                            }}
                                                        >
                                                            {
                                                                event.time
                                                            }
                                                        </span>

                                                        <p
                                                            className={`truncate text-xs font-semibold ${
                                                                event.completed
                                                                    ? "text-[#9A8A82] line-through"
                                                                    : ""
                                                            }`}
                                                            style={{
                                                                color: event.completed
                                                                    ? undefined
                                                                    : TEXT_PRIMARY,
                                                            }}
                                                        >
                                                            {
                                                                event.title
                                                            }
                                                        </p>
                                                    </div>

                                                    <div className="mt-0.5 flex items-center gap-1.5">
                                                        <span
                                                            className="rounded border border-[#CABDB2]/50 bg-[#FFFBF0] px-1.5 py-0.5 text-[9px] font-medium"
                                                            style={{
                                                                color: TEXT_SECONDARY,
                                                            }}
                                                        >
                                                            {
                                                                event.category
                                                            }
                                                        </span>

                                                        <span
                                                            className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-bold text-white ${config.color}`}
                                                        >
                                                            <span className="h-1 w-1 rounded-full bg-white/80" />
                                                            {
                                                                config.label
                                                            }
                                                        </span>
                                                    </div>
                                                </div>

                                                <button
                                                    onClick={() =>
                                                        deleteEvent(
                                                            event.id
                                                        )
                                                    }
                                                    className="rounded p-1 text-[#CABDB2] opacity-0 transition group-hover:opacity-100 hover:bg-[#FEF2F2] hover:text-[#EF4444]"
                                                    aria-label="Delete event"
                                                >
                                                    <Trash2
                                                        size={
                                                            14
                                                        }
                                                    />
                                                </button>
                                            </div>
                                        );
                                    }
                                )
                            )}
                        </div>
                    </div>
                </div>

                {/* ------------------------------------------------------------------ */}
                {/* Right column                                                       */}
                {/* ------------------------------------------------------------------ */}

                <div className="flex min-h-0 flex-col gap-3">
                    {/* Upcoming week */}
                    <div className="rounded-xl border border-[#CABDB2]/70 bg-white/60 p-3 shadow-md shadow-[#CA8A78]/6 backdrop-blur-md">
                        <div className="mb-2.5 flex items-center gap-2">
                            <CalendarDays
                                size={14}
                                className="text-[#CA8A78]"
                            />

                            <h3
                                className="text-xs font-bold tracking-tight"
                                style={{
                                    color: TEXT_PRIMARY,
                                }}
                            >
                                Upcoming Week
                            </h3>
                        </div>

                        <div className="grid grid-cols-7 gap-1.5">
                            {weekEventCounts.map(
                                (day) => (
                                    <button
                                        key={day.date.toISOString()}
                                        onClick={() =>
                                            setSelectedDate(
                                                day.date
                                            )
                                        }
                                        className={`
                                            flex flex-col items-center gap-1 rounded-lg border p-1.5 transition-all duration-150
                                            ${
                                                day.isToday
                                                    ? "border-[#CA8A78] bg-[#FFFBF0] shadow-sm"
                                                    : "border-[#CABDB2]/50 bg-white/50 hover:border-[#CA8A78]/30"
                                            }
                                        `}
                                    >
                                        <span
                                            className="text-[9px] font-bold uppercase"
                                            style={{
                                                color: day.isToday
                                                    ? ACCENT
                                                    : TEXT_MUTED,
                                            }}
                                        >
                                            {format(
                                                day.date,
                                                "EEE"
                                            )}
                                        </span>

                                        <span
                                            className="text-sm font-bold leading-none"
                                            style={{
                                                color: day.isToday
                                                    ? ACCENT
                                                    : TEXT_PRIMARY,
                                            }}
                                        >
                                            {format(
                                                day.date,
                                                "d"
                                            )}
                                        </span>

                                        {day.count >
                                            0 && (
                                            <span className="rounded-full bg-[#CA8A78]/10 px-1.5 py-0.5 text-[9px] font-bold text-[#CA8A78]">
                                                {
                                                    day.count
                                                }
                                            </span>
                                        )}
                                    </button>
                                )
                            )}
                        </div>
                    </div>

                    {/* Summary */}
                    <div className="rounded-xl border border-[#CABDB2]/70 bg-white/60 p-3 shadow-md shadow-[#CA8A78]/6 backdrop-blur-md">
                        <div className="mb-2.5 flex items-center gap-2">
                            <div className="rounded-lg border border-[#CA8A78]/20 bg-[#CA8A78]/10 p-1.5">
                                <Sparkles
                                    size={14}
                                    className="text-[#CA8A78]"
                                />
                            </div>

                            <h3
                                className="text-xs font-bold tracking-tight"
                                style={{
                                    color: TEXT_PRIMARY,
                                }}
                            >
                                Schedule Summary
                            </h3>
                        </div>

                        <div className="space-y-2.5">
                            <div>
                                <div className="mb-1 flex items-center justify-between">
                                    <span
                                        className="text-[10px] font-medium"
                                        style={{
                                            color: TEXT_SECONDARY,
                                        }}
                                    >
                                        Workload
                                    </span>

                                    <span
                                        className="text-[10px] font-bold"
                                        style={{
                                            color: TEXT_PRIMARY,
                                        }}
                                    >
                                        {
                                            workloadPercent
                                        }
                                        %
                                    </span>
                                </div>

                                <div className="h-1.5 overflow-hidden rounded-full border border-[#CABDB2]/50 bg-[#FFFBF0]">
                                    <div
                                        className="h-full rounded-full bg-[#CA8A78] transition-all duration-500"
                                        style={{
                                            width: `${workloadPercent}%`,
                                        }}
                                    />
                                </div>
                            </div>

                            <div className="flex items-center justify-between">
                                <span
                                    className="text-[10px] font-medium"
                                    style={{
                                        color: TEXT_SECONDARY,
                                    }}
                                >
                                    Free days this week
                                </span>

                                <span
                                    className="text-xs font-bold"
                                    style={{
                                        color: TEXT_PRIMARY,
                                    }}
                                >
                                    {freeSlots}
                                </span>
                            </div>

                            <div className="flex items-center justify-between">
                                <span
                                    className="text-[10px] font-medium"
                                    style={{
                                        color: TEXT_SECONDARY,
                                    }}
                                >
                                    Total events
                                </span>

                                <span
                                    className="text-xs font-bold"
                                    style={{
                                        color: TEXT_PRIMARY,
                                    }}
                                >
                                    {events.length}
                                </span>
                            </div>

                            {overdueEvents.length >
                                0 && (
                                <div className="flex items-center gap-1.5 rounded-md border border-[#FECACA] bg-[#FEF2F2] px-2 py-1.5">
                                    <AlertCircle
                                        size={12}
                                        className="text-[#EF4444]"
                                    />

                                    <span className="text-[10px] font-bold text-[#DC2626]">
                                        {
                                            overdueEvents.length
                                        }{" "}
                                        overdue
                                    </span>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Chart */}
                    <div className="min-h-0 flex-1">
                        <PriorityLineChart
                            events={events}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}

