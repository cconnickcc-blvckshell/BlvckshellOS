"use client";

import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";

export type CoreState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "delegating"
  | "error";

export interface BlvckbotCoreProps {
  state: CoreState;
  delegatingTo?: string;
  micAmplitude?: number;
  dropActive?: boolean;
  className?: string;
  onDrop?: (files: FileList) => void;
}

const RING_SPEED: Record<CoreState, { outer: number; mid: number; inner: number }> = {
  idle: { outer: 60, mid: 45, inner: 20 },
  listening: { outer: 30, mid: 22, inner: 10 },
  thinking: { outer: 12, mid: 8, inner: 5 },
  speaking: { outer: 25, mid: 18, inner: 12 },
  delegating: { outer: 20, mid: 14, inner: 8 },
  error: { outer: 40, mid: 30, inner: 15 },
};

export function BlvckbotCore({
  state,
  delegatingTo,
  micAmplitude = 0,
  dropActive = false,
  className = "",
  onDrop,
}: BlvckbotCoreProps) {
  const speeds = RING_SPEED[state];
  const active = state !== "idle";
  const amp = Math.min(1, Math.max(0, micAmplitude));

  return (
    <div
      className={clsx(
        "relative flex items-center justify-center",
        dropActive && "ring-2 ring-cyan-accent/50",
        className,
      )}
      onDragOver={(e) => {
        e.preventDefault();
      }}
      onDrop={(e) => {
        e.preventDefault();
        if (e.dataTransfer.files?.length && onDrop) {
          onDrop(e.dataTransfer.files);
        }
      }}
    >
      <svg viewBox="0 0 240 240" className="h-full w-full max-h-[320px] max-w-[320px]">
        <defs>
          <filter id="core-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="8" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <radialGradient id="core-radial" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#A855F7" stopOpacity="0.9" />
            <stop offset="70%" stopColor="#7B2FBE" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#080810" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Radiance */}
        <motion.circle
          cx="120"
          cy="120"
          fill="url(#core-radial)"
          filter="url(#core-glow)"
          animate={{
            r: state === "listening" ? [70 + amp * 20, 85 + amp * 25, 70 + amp * 20] : [68, 78, 68],
            opacity:
              state === "error"
                ? [0.2, 0.5, 0.2]
                : active
                  ? [0.25, 0.45, 0.25]
                  : [0.12, 0.28, 0.12],
          }}
          transition={{
            repeat: Infinity,
            duration: state === "listening" ? 1.2 : 3.2,
            ease: "easeInOut",
          }}
        />

        {/* Outermost ring */}
        <motion.g
          style={{ originX: "120px", originY: "120px" }}
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: speeds.outer, ease: "linear" }}
        >
          <circle
            cx="120"
            cy="120"
            r="108"
            fill="none"
            stroke="#1A1A2E"
            strokeWidth="1"
            strokeOpacity="0.6"
          />
        </motion.g>

        {/* Outer ring counter */}
        <motion.g
          style={{ originX: "120px", originY: "120px" }}
          animate={{ rotate: -360 }}
          transition={{ repeat: Infinity, duration: speeds.mid * 1.2, ease: "linear" }}
        >
          <circle
            cx="120"
            cy="120"
            r="96"
            fill="none"
            stroke="#7B2FBE"
            strokeWidth="1.5"
            strokeOpacity={active ? 0.5 : 0.25}
          />
        </motion.g>

        {/* Middle ring arcs */}
        <motion.g
          style={{ originX: "120px", originY: "120px" }}
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: speeds.mid, ease: "linear" }}
        >
          <circle
            cx="120"
            cy="120"
            r="78"
            fill="none"
            stroke="#A855F7"
            strokeWidth="2"
            strokeDasharray="40 20 15 25"
            strokeOpacity={active ? 0.7 : 0.35}
          />
        </motion.g>

        {/* Inner ring */}
        <motion.g
          style={{ originX: "120px", originY: "120px" }}
          animate={{ rotate: state === "thinking" ? -360 : 360 }}
          transition={{ repeat: Infinity, duration: speeds.inner, ease: "linear" }}
        >
          <circle
            cx="120"
            cy="120"
            r="58"
            fill="none"
            stroke="#22D3EE"
            strokeWidth="1"
            strokeDasharray="8 12"
            strokeOpacity={active ? 0.6 : 0.2}
          />
        </motion.g>

        {/* Mic waveform arc when listening */}
        {state === "listening" && (
          <motion.circle
            cx="120"
            cy="120"
            r={100 + amp * 18}
            fill="none"
            stroke="#EF4444"
            strokeWidth="2"
            strokeOpacity={0.3 + amp * 0.5}
            animate={{ strokeOpacity: [0.3 + amp * 0.3, 0.7, 0.3 + amp * 0.3] }}
            transition={{ repeat: Infinity, duration: 0.4 }}
          />
        )}

        {/* Speaking ripples */}
        <AnimatePresence>
          {state === "speaking" &&
            [0, 1, 2].map((i) => (
              <motion.circle
                key={i}
                cx="120"
                cy="120"
                fill="none"
                stroke="#A855F7"
                strokeWidth="1"
                initial={{ r: 40, opacity: 0.5 }}
                animate={{ r: 110, opacity: 0 }}
                transition={{
                  repeat: Infinity,
                  duration: 2,
                  delay: i * 0.65,
                  ease: "easeOut",
                }}
              />
            ))}
        </AnimatePresence>

        {/* Error wash */}
        {state === "error" && (
          <motion.circle
            cx="120"
            cy="120"
            r="50"
            fill="#EF4444"
            initial={{ opacity: 0.4 }}
            animate={{ opacity: [0.4, 0.15, 0.4] }}
            transition={{ repeat: 3, duration: 0.35 }}
          />
        )}

        {/* Core */}
        <motion.circle
          cx="120"
          cy="120"
          r="36"
          fill={state === "error" ? "#EF4444" : "#7B2FBE"}
          filter="url(#core-glow)"
          animate={{
            scale: state === "thinking" ? [1, 1.08, 1] : [1, 1.03, 1],
            opacity: state === "delegating" ? [0.7, 0.9, 0.7] : 1,
          }}
          transition={{ repeat: Infinity, duration: state === "thinking" ? 0.8 : 3 }}
        />

        {/* Reactor glyph */}
        <path
          d="M120 100 L135 125 L105 125 Z"
          fill="none"
          stroke="#E8E8F0"
          strokeWidth="1.5"
          strokeOpacity={active ? 0.9 : 0.4}
        />
        <path
          d="M120 128 Q120 140 108 145 M120 128 Q120 140 132 145"
          fill="none"
          stroke="#22D3EE"
          strokeWidth="1"
          strokeOpacity={active ? 0.7 : 0.25}
        />

        {/* Eye arcs */}
        <path
          d="M95 108 Q100 102 108 105"
          fill="none"
          stroke="#A855F7"
          strokeWidth="2"
          strokeLinecap="round"
          opacity={active ? 0.9 : 0.3}
        />
        <path
          d="M145 108 Q140 102 132 105"
          fill="none"
          stroke="#A855F7"
          strokeWidth="2"
          strokeLinecap="round"
          opacity={active ? 0.9 : 0.3}
        />

        {/* Scan lines */}
        {[0, 1, ...(state === "thinking" ? [2] : [])].map((i) => (
          <motion.line
            key={i}
            x1="40"
            x2="200"
            y1={100 + i * 20}
            y2={100 + i * 20}
            stroke="#A855F7"
            strokeOpacity={0.25}
            strokeWidth="1"
            animate={{ y1: [80, 160, 80], y2: [80, 160, 80] }}
            transition={{
              repeat: Infinity,
              duration: state === "thinking" ? 1.5 : 3,
              delay: i * 0.4,
              ease: "linear",
            }}
          />
        ))}

        {/* Orbiting dots when thinking */}
        {state === "thinking" &&
          [0, 120, 240].map((deg, i) => (
            <motion.circle
              key={i}
              r="3"
              fill="#22D3EE"
              animate={{ rotate: 360 }}
              style={{ originX: "120px", originY: "120px" }}
              transition={{ repeat: Infinity, duration: 4, delay: i * 0.3, ease: "linear" }}
              cx={120 + 88 * Math.cos((deg * Math.PI) / 180)}
              cy={120 + 88 * Math.sin((deg * Math.PI) / 180)}
            />
          ))}
      </svg>

      {dropActive && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <p className="rounded-lg bg-surface/90 px-4 py-2 font-mono text-xs text-cyan-accent">
            Drop to share with Blvckbot
          </p>
        </div>
      )}

      {delegatingTo && state === "delegating" && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="absolute -bottom-2 font-mono text-[10px] uppercase tracking-widest text-cyan-accent"
        >
          → {delegatingTo}
        </motion.div>
      )}
    </div>
  );
}
