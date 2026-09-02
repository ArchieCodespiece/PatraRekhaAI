/**
 * Shared Framer Motion animation variants for PatraRekha landing + auth pages.
 * Import from here instead of duplicating variant definitions per component.
 */

export const fadeUp = {
    hidden: { opacity: 0, y: 24 },
    visible: {
        opacity: 1,
        y: 0,
        transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
    },
};

export const fadeIn = {
    hidden: { opacity: 0 },
    visible: {
        opacity: 1,
        transition: { duration: 0.45, ease: "easeOut" },
    },
};

export const staggerContainer = {
    hidden: { opacity: 0 },
    visible: {
        opacity: 1,
        transition: {
            staggerChildren: 0.08,
            delayChildren: 0.05,
        },
    },
};

export const staggerContainerSlow = {
    hidden: { opacity: 0 },
    visible: {
        opacity: 1,
        transition: {
            staggerChildren: 0.14,
            delayChildren: 0.1,
        },
    },
};

export const slideInLeft = {
    hidden: { opacity: 0, x: -32 },
    visible: {
        opacity: 1,
        x: 0,
        transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] },
    },
};

export const slideInRight = {
    hidden: { opacity: 0, x: 32 },
    visible: {
        opacity: 1,
        x: 0,
        transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] },
    },
};

export const scaleIn = {
    hidden: { opacity: 0, scale: 0.94 },
    visible: {
        opacity: 1,
        scale: 1,
        transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] },
    },
};

/** Navbar entrance — slides down from above */
export const navbarVariant = {
    hidden: { opacity: 0, y: -20 },
    visible: {
        opacity: 1,
        y: 0,
        transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
    },
};

/** Pipeline step — used in the hero product visual */
export const pipelineStep = {
    hidden: { opacity: 0, y: 16, scale: 0.96 },
    visible: {
        opacity: 1,
        y: 0,
        scale: 1,
        transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
    },
};

/** For the auth card */
export const authCardVariant = {
    hidden: { opacity: 0, y: 28, scale: 0.97 },
    visible: {
        opacity: 1,
        y: 0,
        scale: 1,
        transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
    },
};

export const errorVariant = {
    hidden: { opacity: 0, y: -8, height: 0 },
    visible: {
        opacity: 1,
        y: 0,
        height: "auto",
        transition: { duration: 0.28, ease: "easeOut" },
    },
    exit: {
        opacity: 0,
        y: -8,
        height: 0,
        transition: { duration: 0.2, ease: "easeIn" },
    },
};
