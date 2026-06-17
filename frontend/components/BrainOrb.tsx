"use client";

import { motion } from "framer-motion";
import type { BrainState } from "@/lib/api";

const STATE_STYLES: Record<
  BrainState,
  { color: string; glow: string; label: string; pulse: boolean; white?: boolean }
> = {
  IDLE: { color: "#7B2FBE", glow: "rgba(123,47,190,0.35)", label: "idle", pulse: false },
  THINKING: {
    color: "#A855F7",
    glow: "rgba(168,85,247,0.6)",
    label: "thinking",
    pulse: true,
  },
  EXECUTING: {
    color: "#FFFFFF",
    glow: "rgba(255,255,255,0.55)",
    label: "executing",
    pulse: true,
    white: true,
  },
  ERROR: { color: "#EF4444", glow: "rgba(239,68,68,0.5)", label: "error", pulse: true },
  OFFLINE: { color: "#33334d", glow: "rgba(51,51,77,0.3)", label: "offline", pulse: false },
};

export function BrainOrb({
  state,
  size = 56,
}: {
  state: BrainState;
  size?: number;
}) {
  const s = STATE_STYLES[state] ?? STATE_STYLES.IDLE;
  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <motion.span
        aria-hidden
        className="absolute rounded-full"
        style={{
          width: size,
          height: size,
          background: `radial-gradient(circle, ${s.color} 0%, ${s.glow} 55%, transparent 72%)`,
          boxShadow: `0 0 ${size / 2}px ${s.glow}`,
        }}
        animate={
          s.pulse
            ? { scale: [0.9, 1.12, 0.9], opacity: [0.65, 1, 0.65] }
            : { scale: [0.94, 1.04, 0.94], opacity: [0.5, 0.8, 0.5] }
        }
        transition={{
          duration: s.pulse ? 1.2 : 3.2,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
      <span
        className="relative rounded-full"
        style={{
          width: size * 0.38,
          height: size * 0.38,
          background: s.color,
          boxShadow: s.white ? "0 0 12px rgba(255,255,255,0.8)" : `0 0 10px ${s.color}`,
        }}
      />
    </div>
  );
}

export function stateLabel(state: BrainState): string {
  return STATE_STYLES[state]?.label ?? "idle";
}
