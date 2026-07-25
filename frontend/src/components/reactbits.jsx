"use client";

import { useEffect, useRef, useState } from "react";

export function BlurText({
    text = "",
    delay = 100,
    className = "",
    animateBy = "words",
}) {
    const elements = animateBy === "words" ? text.split(" ") : text.split("");
    const [inView, setInView] = useState(true);
    const ref = useRef(null);

    useEffect(() => {
        if (!ref.current) return;
        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting) {
                    setInView(true);
                    observer.unobserve(ref.current);
                }
            },
            { threshold: 0.1 }
        );
        observer.observe(ref.current);
        return () => observer.disconnect();
    }, []);

    return (
        <p ref={ref} className={`flex w-full flex-wrap justify-center ${className}`}>
            {elements.map((el, i) => (
                <span
                    key={i}
                    className="inline-block transition-all duration-700 ease-out"
                    style={{
                        transitionDelay: `${i * delay}ms`,
                        filter: inView ? "blur(0px)" : "blur(12px)",
                        opacity: inView ? 1 : 0,
                        transform: inView ? "translateY(0)" : "translateY(20px)",
                    }}
                >
                    {el}
                    {animateBy === "words" && "\u00A0"}
                </span>
            ))}
        </p>
    );
}

export function SplitText({
    text = "",
    delay = 60,
    className = "",
    animateBy = "words",
}) {
    const pieces = animateBy === "words" ? text.split(" ") : text.split("");
    const [inView, setInView] = useState(true);
    const ref = useRef(null);

    useEffect(() => {
        if (!ref.current) return;
        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting) {
                    setInView(true);
                    observer.unobserve(ref.current);
                }
            },
            { threshold: 0.2 }
        );
        observer.observe(ref.current);
        return () => observer.disconnect();
    }, []);

    return (
        <h2 ref={ref} className={`flex w-full flex-wrap justify-center ${className}`}>
            {pieces.map((piece, i) => (
                <span
                    key={`${piece}-${i}`}
                    className="inline-block transition-all duration-700 ease-out"
                    style={{
                        transitionDelay: `${i * delay}ms`,
                        opacity: inView ? 1 : 0,
                        transform: inView ? "translateY(0)" : "translateY(18px)",
                        filter: inView ? "blur(0px)" : "blur(8px)",
                    }}
                >
                    {piece}
                    {animateBy === "words" && "\u00A0"}
                </span>
            ))}
        </h2>
    );
}

export function GradientText({
    children,
    className = "",
    colors = ["#CA8A78", "#413632", "#CABDB2", "#CA8A78"],
    animationSpeed = 6,
}) {
    return (
        <span
            className={`inline-block bg-clip-text text-transparent ${className}`}
            style={{
                backgroundImage: `linear-gradient(90deg, ${colors.join(", ")})`,
                backgroundSize: "300% 100%",
                animation: `gradient-shift ${animationSpeed}s ease infinite`,
            }}
        >
            {children}
            <style jsx>{`
                @keyframes gradient-shift {
                    0% { background-position: 0% 50%; }
                    50% { background-position: 100% 50%; }
                    100% { background-position: 0% 50%; }
                }
            `}</style>
        </span>
    );
}

export function AnimatedCounter({ target, duration = 2000, className = "" }) {
    const [count, setCount] = useState(0);
    const [inView, setInView] = useState(false);
    const ref = useRef(null);

    useEffect(() => {
        if (!ref.current) return;
        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting) {
                    setInView(true);
                    observer.unobserve(ref.current);
                }
            },
            { threshold: 0.1 }
        );
        observer.observe(ref.current);
        return () => observer.disconnect();
    }, []);

    useEffect(() => {
        if (!inView) return;
        let start = 0;
        const step = target / (duration / 16);
        const timer = setInterval(() => {
            start += step;
            if (start >= target) {
                setCount(target);
                clearInterval(timer);
            } else {
                setCount(Math.floor(start));
            }
        }, 16);
        return () => clearInterval(timer);
    }, [inView, target, duration]);

    return (
        <span ref={ref} className={className}>
            {count.toLocaleString()}
        </span>
    );
}

export function FadeInOnScroll({ children, className = "", delay = 0 }) {
    const [inView, setInView] = useState(false);
    const ref = useRef(null);

    useEffect(() => {
        if (!ref.current) return;
        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting) {
                    setInView(true);
                    observer.unobserve(ref.current);
                }
            },
            { threshold: 0.1 }
        );
        observer.observe(ref.current);
        return () => observer.disconnect();
    }, []);

    return (
        <div
            ref={ref}
            className={`transition-all duration-700 ease-out ${className}`}
            style={{
                transitionDelay: `${delay}ms`,
                opacity: inView ? 1 : 0,
                transform: inView ? "translateY(0)" : "translateY(30px)",
            }}
        >
            {children}
        </div>
    );
}

export function SpotlightCard({ children, className = "" }) {
    const ref = useRef(null);
    const [pos, setPos] = useState({ x: 0, y: 0 });
    const [isHovering, setIsHovering] = useState(false);

    const handleMouseMove = (e) => {
        if (!ref.current) return;
        const rect = ref.current.getBoundingClientRect();
        setPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    };

    return (
        <div
            ref={ref}
            onMouseMove={handleMouseMove}
            onMouseEnter={() => setIsHovering(true)}
            onMouseLeave={() => setIsHovering(false)}
            className={`relative overflow-hidden rounded-2xl border border-[#CABDB2]/40 bg-[#FFEAD5]/50 backdrop-blur-sm transition-all duration-300 hover:border-[#CA8A78]/70 hover:bg-[#F1DDCA] hover:shadow-xl hover:shadow-[#CA8A78]/10 ${className}`}
        >
            {/* Spotlight gradient overlay */}
            <div
                className="pointer-events-none absolute inset-0 transition-opacity duration-300"
                style={{
                    opacity: isHovering ? 1 : 0,
                    background: `radial-gradient(600px circle at ${pos.x}px ${pos.y}px, rgba(202,138,120,0.12), transparent 40%)`,
                }}
            />
            <div className="relative z-10">{children}</div>
        </div>
    );
}

export function Marquee({ children, speed = 30, direction = "left", className = "" }) {
    return (
        <div className={`overflow-hidden whitespace-nowrap ${className}`}>
            <div
                className="inline-flex"
                style={{
                    animation: `marquee-${direction} ${speed}s linear infinite`,
                }}
            >
                {children}
                {children}
            </div>
            <style jsx>{`
                @keyframes marquee-left {
                    0% { transform: translateX(0); }
                    100% { transform: translateX(-50%); }
                }
                @keyframes marquee-right {
                    0% { transform: translateX(-50%); }
                    100% { transform: translateX(0); }
                }
            `}</style>
        </div>
    );
}
