"use client";

import { useEffect, useRef } from "react";
import type { CoreState } from "./BlvckbotCore";
import type { PulseTracker } from "@/lib/speechPulse";

export interface ParticleFieldProps {
  state: CoreState;
  micAmplitude?: number;
  pulseTracker?: PulseTracker;
  color: string;
  accentColor?: string;
  className?: string;
}

interface Particle {
  angle: number;
  baseRadius: number;
  radiusJitter: number;
  speed: number;
  size: number;
  phase: number;
  accent: boolean;
}

const COUNT = 90;

const SPEED_MULTIPLIER: Record<CoreState, number> = {
  idle: 0.5,
  listening: 1.5,
  thinking: 2.4,
  speaking: 1.6,
  delegating: 1.8,
  error: 1.1,
};

function hexToRgb(hex: string) {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const n = parseInt(full, 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

function makeGlowSprite(hex: string) {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;
  const { r, g, b } = hexToRgb(hex);
  const grad = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.16, `rgba(${r},${g},${b},0.95)`);
  grad.addColorStop(0.5, `rgba(${r},${g},${b},0.35)`);
  grad.addColorStop(1, `rgba(${r},${g},${b},0)`);
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);
  return canvas;
}

export function ParticleField({
  state,
  micAmplitude = 0,
  pulseTracker,
  color,
  accentColor = "#22D3EE",
  className = "",
}: ParticleFieldProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<Particle[]>([]);
  const ampRef = useRef(0);
  const stateRef = useRef(state);
  const spriteRef = useRef<HTMLCanvasElement | null>(null);
  const accentSpriteRef = useRef<HTMLCanvasElement | null>(null);
  const trailsRef = useRef<Map<number, { x: number; y: number }>>(new Map());

  useEffect(() => {
    stateRef.current = state;
  }, [state]);
  useEffect(() => {
    ampRef.current = Math.min(1, Math.max(0, micAmplitude));
  }, [micAmplitude]);
  useEffect(() => {
    spriteRef.current = makeGlowSprite(color);
  }, [color]);
  useEffect(() => {
    accentSpriteRef.current = makeGlowSprite(accentColor);
  }, [accentColor]);

  useEffect(() => {
    if (particlesRef.current.length) return;
    const particles: Particle[] = [];
    for (let i = 0; i < COUNT; i++) {
      particles.push({
        angle: Math.random() * Math.PI * 2,
        baseRadius: 58 + Math.random() * 82,
        radiusJitter: 4 + Math.random() * 14,
        speed: (0.08 + Math.random() * 0.22) * (Math.random() < 0.5 ? 1 : -1),
        size: 1.2 + Math.random() * 2.6,
        phase: Math.random() * Math.PI * 2,
        accent: Math.random() < 0.22,
      });
    }
    particlesRef.current = particles;
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    const parent = canvas?.parentElement;
    if (!canvas || !parent) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    let last = performance.now();

    // Canvas is a replaced element, so CSS inset percentages don't stretch it like a div —
    // size and position the bleed explicitly here instead.
    const BLEED = 0.09;
    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = parent.getBoundingClientRect();
      const bleedW = rect.width * BLEED;
      const bleedH = rect.height * BLEED;
      const w = rect.width + bleedW * 2;
      const h = rect.height + bleedH * 2;
      canvas.style.left = `${-bleedW}px`;
      canvas.style.top = `${-bleedH}px`;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      canvas.width = Math.max(1, w * dpr);
      canvas.height = Math.max(1, h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(parent);

    const tick = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;

      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      const cx = w / 2;
      const cy = h / 2;
      const scale = Math.min(w, h) / 240;

      ctx.clearRect(0, 0, w, h);
      ctx.globalCompositeOperation = "lighter";

      const cur = stateRef.current;
      const speedMul = SPEED_MULTIPLIER[cur];
      const active = cur !== "idle";

      let amp = ampRef.current;
      if (cur === "speaking" && pulseTracker) {
        amp = Math.min(1, 0.18 + pulseTracker.sample(now) * 0.95);
      } else if (cur !== "listening") {
        amp = 0.15;
      }

      const sprite = spriteRef.current;
      const accentSprite = accentSpriteRef.current;

      for (let idx = 0; idx < particlesRef.current.length; idx++) {
        const p = particlesRef.current[idx];
        p.angle += p.speed * speedMul * dt;
        const wobble =
          Math.sin(now / 1000 + p.phase) * p.radiusJitter * (0.3 + amp * 1.4);
        const r = (p.baseRadius + wobble) * scale;
        const x = cx + Math.cos(p.angle) * r;
        const y = cy + Math.sin(p.angle) * r * 0.94;

        const size = p.size * scale * (1 + amp * 1.1);
        const alpha = (active ? 0.5 : 0.3) + amp * 0.5;

        // Faint motion trail so particles read as streaks of energy, not dots.
        const prev = trailsRef.current.get(idx);
        if (prev) {
          ctx.strokeStyle = p.accent ? accentColor : color;
          ctx.globalAlpha = Math.min(0.4, alpha * 0.4);
          ctx.lineWidth = Math.max(0.5, size * 0.5);
          ctx.beginPath();
          ctx.moveTo(prev.x, prev.y);
          ctx.lineTo(x, y);
          ctx.stroke();
        }
        trailsRef.current.set(idx, { x, y });

        const glow = sprite && (p.accent ? accentSprite : sprite);
        ctx.globalAlpha = Math.min(1, alpha);
        const draw = size * 7;
        if (glow) {
          ctx.drawImage(glow, x - draw / 2, y - draw / 2, draw, draw);
        }
      }

      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "source-over";
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [color, accentColor, pulseTracker]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className={`pointer-events-none absolute ${className}`}
    />
  );
}
