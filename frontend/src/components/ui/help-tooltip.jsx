"use client";

import { useState } from "react";
import { HelpCircle } from "lucide-react";

export function HelpTooltip({ content, children }) {
    const [show, setShow] = useState(false);

    return (
        <span
            className="relative inline-flex"
            onMouseEnter={() => setShow(true)}
            onMouseLeave={() => setShow(false)}
            onFocus={() => setShow(true)}
            onBlur={() => setShow(false)}
        >
            {children || (
                <HelpCircle size={12} className="text-muted-foreground/50 hover:text-muted-foreground cursor-help transition-colors" />
            )}
            {show && (
                <span className="absolute bottom-full left-1/2 z-50 mb-2 w-56 -translate-x-1/2 rounded-lg border border-border bg-background p-2 text-xs text-muted-foreground shadow-md">
                    {content}
                    <span className="absolute left-1/2 top-full h-0 w-0 -translate-x-1/2 border-l-4 border-r-4 border-t-4 border-transparent border-t-border" />
                </span>
            )}
        </span>
    );
}
