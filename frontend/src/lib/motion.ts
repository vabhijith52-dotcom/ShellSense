import type { Transition, Variants } from "framer-motion";

/**
 * ShellSense Motion System Tokens
 * Strictly adherence to Section 17 Animation Specification
 */
export const MOTION_DURATIONS = {
  fast: 0.15, // 150ms
  base: 0.25, // 250ms
  slow: 0.4,  // 400ms
  reduced: 0.1, // <=100ms for reduced-motion
} as const;

export const MOTION_EASINGS = {
  standard: [0.2, 0, 0, 1] as const,
  emphasized: [0.16, 1, 0.3, 1] as const,
} as const;

export const MOTION_SPRINGS = {
  modal: {
    type: "spring",
    stiffness: 300,
    damping: 30,
  } satisfies Transition,
  layout: {
    type: "spring",
    stiffness: 400,
    damping: 35,
  } satisfies Transition,
} as const;

// Transition presets
export const TRANSITIONS = {
  fast: {
    duration: MOTION_DURATIONS.fast,
    ease: MOTION_EASINGS.standard,
  } satisfies Transition,
  base: {
    duration: MOTION_DURATIONS.base,
    ease: MOTION_EASINGS.standard,
  } satisfies Transition,
  emphasized: {
    duration: MOTION_DURATIONS.base,
    ease: MOTION_EASINGS.emphasized,
  } satisfies Transition,
  layout: MOTION_SPRINGS.layout,
} as const;

// Standard Reusable Variants
export const pageTransitionVariants: Variants = {
  initial: { opacity: 0, y: 12 },
  animate: {
    opacity: 1,
    y: 0,
    transition: {
      duration: MOTION_DURATIONS.base,
      ease: MOTION_EASINGS.emphasized,
    },
  },
  exit: {
    opacity: 0,
    y: -8,
    transition: {
      duration: MOTION_DURATIONS.fast,
      ease: MOTION_EASINGS.standard,
    },
  },
};

export const modalBackdropVariants: Variants = {
  initial: { opacity: 0, backdropFilter: "blur(0px)" },
  animate: {
    opacity: 1,
    backdropFilter: "blur(8px)",
    transition: { duration: 0.2 },
  },
  exit: {
    opacity: 0,
    backdropFilter: "blur(0px)",
    transition: { duration: MOTION_DURATIONS.fast },
  },
};

export const modalPanelVariants: Variants = {
  initial: { opacity: 0, scale: 0.96, y: 8 },
  animate: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: MOTION_SPRINGS.modal,
  },
  exit: {
    opacity: 0,
    scale: 0.96,
    y: 8,
    transition: { duration: MOTION_DURATIONS.fast },
  },
};

export const staggerContainer = (staggerChildren = 0.04): Variants => ({
  initial: {},
  animate: {
    transition: {
      staggerChildren,
    },
  },
});

export const staggerItem: Variants = {
  initial: { opacity: 0, y: 6 },
  animate: {
    opacity: 1,
    y: 0,
    transition: {
      duration: MOTION_DURATIONS.base,
      ease: MOTION_EASINGS.standard,
    },
  },
};
