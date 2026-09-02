# PatraRekha UI motion layer

Phase 1 adds small reusable motion primitives without changing existing product logic.

- `MotionCard`: subtle entrance + hover lift
- `PageTransition`: page/content entrance
- `AnimatedButton`: restrained hover/tap feedback
- `StatusPill`: status indicator
- `Skeleton` / `CardSkeleton`: loading states
- `ExpandableSource`: expandable document/source excerpt

These use the existing `motion/react` dependency already present in the project.
Use them selectively; keep enterprise screens restrained and accessible.
