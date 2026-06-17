"use client";

import { motion } from "framer-motion";
import type { BrainStatus } from "@/lib/types";

const STATE_STYLES: Record<
  BrainStatus,
  { core: string; glow: string; ring: boolean; label: string }
> = {
  idle: { core: "#7B2FBE", glow: "rgba(123,47,190,0.35)", ring: false, label: "idle" },
  thinking: { core: "#A855F7", glow: "rgba(168,85,247,0.65)", ring: true, label: "thinking" },
  executing: { core: "#FFFFFF", glow: "rgba(255,255,255,0.7)", ring: true, label: "executing" },
  error: { core: "#EF4444", glow: "rgba(239,68,68,0.6)", ring: true, label: "error" },
  offline: { core: "#2A2A44", glow: "rgba(42,42,68,0.4)", ring: false, label: "offline" },
};

interface BrainOrbProps {
  status: BrainStatus;
  size?: number;
  label?: string;
}

/** A pulsing orb representing a brain's live state. The system feels alive. */
export function BrainOrb({ status, size = 56, label }: BrainOrbProps) {
  const style = STATE_STYLES[status] ?? STATE_STYLES.idle;
  const animate =
    status === "thinking" || status === "executing" || status === "error";

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size, height: size }}
      title={label ? `${label}: ${style.label}` : style.label}
    >
      {style.ring && (
        <span
          className="absolute rounded-full"
          style={{
            width: size,
            height: size,
            border: `2px solid ${style.core}`,
            animation: "pulse-ring 2s ease-out infinite",
          }}
        />
      )}
      <motion.span
        className="rounded-full"
        style={{
          width: size * 0.6,
          height: size * 0.6,
          background: `radial-gradient(circle at 35% 30%, ${style.core}, ${style.glow})`,
          boxShadow: `0 0 ${size * 0.4}px ${style.glow}`,
        }}
        animate={
          animate
            ? { scale: [1, 1.12, 1], opacity: [0.85, 1, 0.85] }
            : { scale: 1, opacity: 0.85 }
        }
        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}
