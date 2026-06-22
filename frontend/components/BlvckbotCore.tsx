"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";
import { ParticleField } from "./ParticleField";
import { VoiceWaveform } from "./VoiceWaveform";
import { createPulseTracker } from "@/lib/speechPulse";

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
  speechText?: string | null;
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

const STATE_COLOR: Record<CoreState, string> = {
  idle: "#A855F7",
  listening: "#22D3EE",
  thinking: "#A855F7",
  speaking: "#A855F7",
  delegating: "#22D3EE",
  error: "#EF4444",
};

const CENTER = 120;
const TAU = Math.PI / 180;

function polar(radius: number, deg: number) {
  const x = Math.round((CENTER + radius * Math.cos(deg * TAU)) * 1000) / 1000;
  const y = Math.round((CENTER + radius * Math.sin(deg * TAU)) * 1000) / 1000;
  return [x, y] as const;
}

export function BlvckbotCore({
  state,
  delegatingTo,
  micAmplitude = 0,
  speechText = null,
  dropActive = false,
  className = "",
  onDrop,
}: BlvckbotCoreProps) {
  const speeds = RING_SPEED[state];
  const active = state !== "idle";
  const amp = Math.min(1, Math.max(0, micAmplitude));
  const hue = STATE_COLOR[state];
  const pulseTracker = useRef(createPulseTracker()).current;
  const prevWordCountRef = useRef(0);

  useEffect(() => {
    if (state !== "speaking" || !speechText) {
      prevWordCountRef.current = 0;
      return;
    }
    const count = speechText.trim().split(/\s+/).filter(Boolean).length;
    if (count > prevWordCountRef.current) {
      pulseTracker.push(1);
      prevWordCountRef.current = count;
    }
  }, [state, speechText, pulseTracker]);

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
      {/* Ambient bloom — soft CSS blur behind the instrument, screen-blended for additive light */}
      <motion.div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-full blur-3xl mix-blend-screen"
        style={{ background: `radial-gradient(circle, ${hue}66 0%, transparent 65%)` }}
        animate={{
          opacity: active ? [0.45, 0.9, 0.45] : [0.2, 0.4, 0.2],
          scale: state === "listening" ? [0.9 + amp * 0.1, 1.12 + amp * 0.2, 0.9 + amp * 0.1] : [0.92, 1.06, 0.92],
        }}
        transition={{ repeat: Infinity, duration: state === "thinking" ? 1.3 : 3.4, ease: "easeInOut" }}
      />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute inset-[18%] rounded-full blur-xl mix-blend-screen"
        style={{ background: `radial-gradient(circle, #ffffff80 0%, ${hue}88 40%, transparent 75%)` }}
        animate={{ opacity: [0.5, 1, 0.5] }}
        transition={{ repeat: Infinity, duration: state === "listening" ? 0.8 : 2.4, ease: "easeInOut" }}
      />

      <ParticleField
        state={state}
        micAmplitude={amp}
        pulseTracker={pulseTracker}
        color={hue}
        accentColor="#22D3EE"
        className="mix-blend-screen"
      />

      {/* Radar sweep — conic gradient ring, additive */}
      <motion.div
        aria-hidden
        className="pointer-events-none absolute inset-[4%] rounded-full mix-blend-screen"
        style={{
          background: `conic-gradient(from 0deg, transparent 0deg, transparent 250deg, ${hue}cc 345deg, transparent 358deg)`,
          maskImage: "radial-gradient(circle, transparent 40%, black 41%, black 100%)",
          WebkitMaskImage: "radial-gradient(circle, transparent 40%, black 41%, black 100%)",
        }}
        animate={{ rotate: 360 }}
        transition={{ repeat: Infinity, duration: speeds.outer * 0.5, ease: "linear" }}
      />

      <svg
        viewBox="0 0 240 240"
        className="relative h-full w-full max-h-[320px] max-w-[320px] mix-blend-screen"
      >
        <defs>
          <filter id="core-glow" x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur stdDeviation="10" result="soft" />
            <feMerge>
              <feMergeNode in="soft" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <radialGradient id="plasma" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.95" />
            <stop offset="35%" stopColor={hue} stopOpacity="0.9" />
            <stop offset="100%" stopColor={hue} stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Outer dial — precision tick marks, slow rotation */}
        <motion.g
          style={{ originX: "120px", originY: "120px" }}
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: speeds.outer, ease: "linear" }}
        >
          <circle cx="120" cy="120" r="112" fill="none" stroke="#2A2A40" strokeWidth="1" strokeOpacity="0.5" />
          {Array.from({ length: 48 }).map((_, i) => {
            const deg = (i / 48) * 360;
            const long = i % 4 === 0;
            const [x1, y1] = polar(112, deg);
            const [x2, y2] = polar(long ? 102 : 107, deg);
            return (
              <line
                key={i}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke={long ? hue : "#3A3A55"}
                strokeWidth={long ? 1.5 : 0.75}
                strokeOpacity={long ? (active ? 0.85 : 0.4) : 0.3}
              />
            );
          })}
        </motion.g>

        {/* Segmented reactor band — thick broken arcs, counter-rotating */}
        <motion.g
          style={{ originX: "120px", originY: "120px" }}
          animate={{ rotate: -360 }}
          transition={{ repeat: Infinity, duration: speeds.mid * 1.3, ease: "linear" }}
        >
          <circle
            cx="120"
            cy="120"
            r="92"
            fill="none"
            stroke={hue}
            strokeWidth="3"
            strokeDasharray="2 16 46 8 28 22"
            strokeLinecap="round"
            strokeOpacity={active ? 0.7 : 0.3}
          />
        </motion.g>

        {/* Fine dashed telemetry ring */}
        <motion.g
          style={{ originX: "120px", originY: "120px" }}
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: speeds.mid, ease: "linear" }}
        >
          <circle
            cx="120"
            cy="120"
            r="76"
            fill="none"
            stroke="#22D3EE"
            strokeWidth="1.5"
            strokeDasharray="3 9"
            strokeOpacity={active ? 0.55 : 0.22}
          />
        </motion.g>

        {/* Aperture blades — inner ring, reverses direction when thinking */}
        <motion.g
          style={{ originX: "120px", originY: "120px" }}
          animate={{ rotate: state === "thinking" ? -360 : 360 }}
          transition={{ repeat: Infinity, duration: speeds.inner, ease: "linear" }}
        >
          {Array.from({ length: 8 }).map((_, i) => {
            const deg = (i / 8) * 360;
            const [x1, y1] = polar(46, deg);
            const [x2, y2] = polar(61, deg);
            return (
              <line
                key={i}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke={hue}
                strokeWidth="2"
                strokeLinecap="round"
                strokeOpacity={active ? 0.75 : 0.3}
              />
            );
          })}
        </motion.g>

        {/* Listening — amplitude-reactive ring */}
        {state === "listening" && (
          <motion.circle
            cx="120"
            cy="120"
            r={100 + amp * 18}
            fill="none"
            stroke="#22D3EE"
            strokeWidth="2"
            strokeOpacity={0.3 + amp * 0.5}
            animate={{ strokeOpacity: [0.3 + amp * 0.3, 0.85, 0.3 + amp * 0.3] }}
            transition={{ repeat: Infinity, duration: 0.35 }}
          />
        )}

        {/* Speaking — outward ripples */}
        <AnimatePresence>
          {state === "speaking" &&
            [0, 1, 2].map((i) => (
              <motion.circle
                key={i}
                cx="120"
                cy="120"
                fill="none"
                stroke={hue}
                strokeWidth="1.5"
                initial={{ r: 38, opacity: 0.6 }}
                animate={{ r: 118, opacity: 0 }}
                transition={{
                  repeat: Infinity,
                  duration: 2,
                  delay: i * 0.6,
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
            animate={{ opacity: [0.4, 0.1, 0.4] }}
            transition={{ repeat: 3, duration: 0.3 }}
          />
        )}

        {/* Plasma core */}
        <motion.circle
          cx="120"
          cy="120"
          r="42"
          fill="url(#plasma)"
          filter="url(#core-glow)"
          animate={{
            scale:
              state === "thinking"
                ? [1, 1.12, 1]
                : state === "listening"
                  ? [1, 1 + amp * 0.25, 1]
                  : [1, 1.04, 1],
            opacity: state === "delegating" ? [0.7, 1, 0.7] : 1,
          }}
          transition={{ repeat: Infinity, duration: state === "thinking" ? 0.7 : 2.8, ease: "easeInOut" }}
        />
        <circle cx="120" cy="120" r="13" fill="#FFFFFF" opacity={active ? 0.95 : 0.65} filter="url(#core-glow)" />

        {/* Orbiting motes — varied radius/speed for parallax depth */}
        {[0, 60, 120, 180, 240, 300].map((deg, i) => {
          const radius = 84 + (i % 3) * 11;
          const size = i % 2 === 0 ? 2.2 : 1.3;
          const [cx, cy] = polar(radius, deg);
          return (
            <motion.circle
              key={deg}
              r={size}
              fill={i % 3 === 0 ? "#22D3EE" : hue}
              style={{ originX: "120px", originY: "120px" }}
              animate={{ rotate: state === "thinking" ? [0, 360] : [0, -360] }}
              transition={{ repeat: Infinity, duration: 7 + i, ease: "linear", delay: i * 0.2 }}
              cx={cx}
              cy={cy}
              opacity={active ? 0.85 : 0.35}
            />
          );
        })}
      </svg>

      {state === "speaking" && (
        <VoiceWaveform
          pulseTracker={pulseTracker}
          active={state === "speaking"}
          color={hue}
          className="absolute -bottom-1 h-7 w-2/3"
        />
      )}

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
