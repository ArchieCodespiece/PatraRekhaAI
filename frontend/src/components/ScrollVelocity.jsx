"use client";

import { useLayoutEffect, useRef, useState } from "react";
import {
    motion,
    useAnimationFrame,
    useMotionValue,
    useScroll,
    useSpring,
    useTransform,
    useVelocity,
} from "motion/react";

function useElementWidth(ref) {
    const [width, setWidth] = useState(0);

    useLayoutEffect(() => {
        const updateWidth = () => setWidth(ref.current?.offsetWidth ?? 0);
        updateWidth();
        window.addEventListener("resize", updateWidth);
        return () => window.removeEventListener("resize", updateWidth);
    }, [ref]);

    return width;
}

function VelocityText({ children, velocity, className, numCopies }) {
    const baseX = useMotionValue(0);
    const { scrollY } = useScroll();
    const scrollVelocity = useVelocity(scrollY);
    const smoothVelocity = useSpring(scrollVelocity, { damping: 50, stiffness: 400 });
    const velocityFactor = useTransform(smoothVelocity, [0, 1000], [0, 5], { clamp: false });
    const copyRef = useRef(null);
    const copyWidth = useElementWidth(copyRef);
    const directionFactor = useRef(1);

    const x = useTransform(baseX, (value) => {
        if (!copyWidth) return "0px";
        const wrapped = ((((value + copyWidth) % copyWidth) + copyWidth) % copyWidth) - copyWidth;
        return `${wrapped}px`;
    });

    useAnimationFrame((_, delta) => {
        let moveBy = directionFactor.current * velocity * (delta / 1000);
        if (velocityFactor.get() < 0) directionFactor.current = -1;
        else if (velocityFactor.get() > 0) directionFactor.current = 1;

        moveBy += directionFactor.current * moveBy * velocityFactor.get();
        baseX.set(baseX.get() + moveBy);
    });

    return (
        <div className="relative overflow-hidden">
            <motion.div className="flex w-max whitespace-nowrap" style={{ x }}>
                {Array.from({ length: numCopies }, (_, index) => (
                    <span key={index} ref={index === 0 ? copyRef : null} className={className}>
                        {children}&nbsp;
                    </span>
                ))}
            </motion.div>
        </div>
    );
}

export default function ScrollVelocity({ texts = [], velocity = 80, className = "", numCopies = 6 }) {
    return (
        <section aria-label="Organizations using PatraRekhaAI">
            {texts.map((text, index) => (
                <VelocityText
                    key={index}
                    velocity={index % 2 ? -velocity : velocity}
                    className={className}
                    numCopies={numCopies}
                >
                    {text}
                </VelocityText>
            ))}
        </section>
    );
}
