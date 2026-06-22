"use client";

import { motion } from "framer-motion";
import type { BrainState } from "@/lib/api";

const STATE_STYLES: Record<
  BrainState,
  { color: string; glow: string; label: string; pulse: boolean; white?: boolean }
> = {
  IDLE: { color: "#7B2FBE", glow: "rgba(123,47,190,0.35)", label: "idle", pulse: false },
  THINKING: { color: "#A855F7", glow: "rgba(168,85,247,0.6)", label: "thinking", pulse: true },
  EXECUTING: { color: "#FFFFFF", glow: "rgba(255,255,255,0.55)", label: "executing", pulse: true, white: true },
  ERROR: { color: "#EF4444", glow: "rgba(239,68,68,0.5)", label: "error", pulse: true },
  OFFLINE: { color: "#33334d", glow: "rgba(51,51,77,0.3)", label: "offline", pulse: false },
};

export function BrainOrb({
  state,
  size = 56,
  variant = "default",
}: {
  state: BrainState;
  size?: number;
  variant?: "default" | "compact";
}) {
  const s = STATE_STYLES[state] ?? STATE_STYLES.IDLE;

  if (variant === "compact") {
    return (
      <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
        <motion.span
          aria-hidden
          className="absolute rounded-full blur-md mix-blend-screen"
          style={{ width: size * 1.3, height: size * 1.3, background: `radial-gradient(circle, ${s.color}55 0%, transparent 70%)` }}
          animate={
            s.pulse
              ? { opacity: [0.45, 0.9, 0.45], scale: [0.9, 1.15, 0.9] }
              : { opacity: [0.25, 0.45, 0.25], scale: [0.95, 1.05, 0.95] }
          }
          transition={{ duration: s.pulse ? 1.1 : 3, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.span
          className="absolute rounded-full border border-primary/30"
          style={{ width: size, height: size }}
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: s.pulse ? 8 : 20, ease: "linear" }}
        />
        <motion.span
          className="absolute rounded-full border border-cyan-accent/40"
          style={{ width: size * 0.72, height: size * 0.72 }}
          animate={{ rotate: -360 }}
          transition={{ repeat: Infinity, duration: s.pulse ? 5 : 14, ease: "linear" }}
        />
        <span
          className="relative rounded-full"
          style={{
            width: size * 0.34,
            height: size * 0.34,
            background: `radial-gradient(circle at 32% 28%, #ffffff 0%, ${s.color} 35%, #05050c 100%)`,
            boxShadow: `0 0 ${size * 0.3}px ${s.glow}, inset 0 -2px 4px rgba(0,0,0,0.5)`,
          }}
        />
      </div>
    );
  }

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      {/* outer ambient bloom, additive */}
      <motion.span
        aria-hidden
        className="absolute rounded-full blur-lg mix-blend-screen"
        style={{
          width: size * 1.6,
          height: size * 1.6,
          background: `radial-gradient(circle, ${s.color}70 0%, transparent 68%)`,
        }}
        animate={
          s.pulse
            ? { opacity: [0.5, 1, 0.5], scale: [0.88, 1.15, 0.88] }
            : { opacity: [0.3, 0.55, 0.3], scale: [0.94, 1.05, 0.94] }
        }
        transition={{ duration: s.pulse ? 1.2 : 3.2, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* slow orbit ring for depth */}
      <motion.span
        aria-hidden
        className="absolute rounded-full"
        style={{ width: size * 0.94, height: size * 0.94, border: `1px solid ${s.color}40` }}
        animate={{ rotate: 360 }}
        transition={{ repeat: Infinity, duration: s.pulse ? 7 : 18, ease: "linear" }}
      />

      {/* glass sphere body — lit top-left, shadowed bottom-right */}
      <span
        className="relative rounded-full"
        style={{
          width: size * 0.52,
          height: size * 0.52,
          background: `radial-gradient(circle at 32% 26%, #ffffff 0%, ${s.color} 30%, ${s.color}cc 58%, #05050c 100%)`,
          boxShadow: `0 0 ${size * 0.45}px ${s.glow}, inset 0 -${size * 0.08}px ${size * 0.12}px rgba(0,0,0,0.55)`,
        }}
      />

      {/* specular highlight */}
      <span
        className="pointer-events-none absolute rounded-full bg-white/80 blur-[1px]"
        style={{
          width: size * 0.13,
          height: size * 0.08,
          transform: `translate(${-size * 0.1}px, ${-size * 0.1}px) rotate(-25deg)`,
        }}
      />
    </div>
  );
}

export function stateLabel(state: BrainState): string {
  return STATE_STYLES[state]?.label ?? "idle";
}
