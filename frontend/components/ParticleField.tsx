"use client";

import { useEffect, useRef } from "react";
import type { CoreState } from "./BlvckbotCore";

export interface ParticleFieldProps {
  state: CoreState;
  micAmplitude?: number;
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

export function ParticleField({
  state,
  micAmplitude = 0,
  color,
  accentColor = "#22D3EE",
  className = "",
}: ParticleFieldProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<Particle[]>([]);
  const ampRef = useRef(0);
  const stateRef = useRef(state);
  const colorRef = useRef(color);
  const accentRef = useRef(accentColor);
  const startRef = useRef(performance.now());

  useEffect(() => {
    stateRef.current = state;
  }, [state]);
  useEffect(() => {
    ampRef.current = Math.min(1, Math.max(0, micAmplitude));
  }, [micAmplitude]);
  useEffect(() => {
    colorRef.current = color;
  }, [color]);
  useEffect(() => {
    accentRef.current = accentColor;
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
        size: 0.6 + Math.random() * 1.8,
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

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = parent.getBoundingClientRect();
      canvas.width = Math.max(1, rect.width * dpr);
      canvas.height = Math.max(1, rect.height * dpr);
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
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
      if (cur === "speaking") {
        const t = (now - startRef.current) / 1000;
        amp =
          0.45 +
          0.4 * Math.sin(t * 5.2) +
          0.25 * Math.sin(t * 11.3 + 1.7) * Math.sin(t * 1.3);
        amp = Math.min(1, Math.max(0, amp));
      } else if (cur !== "listening") {
        amp = 0.15;
      }

      for (const p of particlesRef.current) {
        p.angle += p.speed * speedMul * dt;
        const wobble =
          Math.sin(now / 1000 + p.phase) * p.radiusJitter * (0.3 + amp * 1.4);
        const r = (p.baseRadius + wobble) * scale;
        const x = cx + Math.cos(p.angle) * r;
        const y = cy + Math.sin(p.angle) * r * 0.94;

        const size = p.size * scale * (1 + amp * 0.8);
        const alpha = (active ? 0.35 : 0.18) + amp * 0.45;

        ctx.beginPath();
        ctx.fillStyle = p.accent ? accentRef.current : colorRef.current;
        ctx.globalAlpha = Math.min(1, alpha);
        ctx.arc(x, y, Math.max(0.4, size), 0, Math.PI * 2);
        ctx.fill();
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
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className={`pointer-events-none absolute inset-0 ${className}`}
    />
  );
}
