"use client";

import { useEffect, useRef } from "react";
import type { PulseTracker } from "@/lib/speechPulse";

export interface VoiceWaveformProps {
  pulseTracker: PulseTracker;
  active: boolean;
  color: string;
  className?: string;
}

const BAR_COUNT = 28;

export function VoiceWaveform({ pulseTracker, active, color, className = "" }: VoiceWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const phasesRef = useRef<number[]>(
    Array.from({ length: BAR_COUNT }, () => Math.random() * Math.PI * 2),
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, rect.width * dpr);
      canvas.height = Math.max(1, rect.height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const tick = (now: number) => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);

      if (active) {
        const env = pulseTracker.sample(now);
        const gap = 3;
        const barWidth = (w - gap * (BAR_COUNT - 1)) / BAR_COUNT;
        ctx.globalCompositeOperation = "lighter";
        for (let i = 0; i < BAR_COUNT; i++) {
          const phase = phasesRef.current[i];
          const ripple = 0.45 + 0.55 * Math.sin(now / 85 + phase);
          const local = Math.max(0, env * ripple);
          const barH = Math.max(2, local * h * 0.95 + 2);
          const x = i * (barWidth + gap);
          const y = (h - barH) / 2;
          ctx.fillStyle = color;
          ctx.globalAlpha = 0.3 + local * 0.7;
          const radius = Math.min(barWidth / 2, 2);
          ctx.beginPath();
          ctx.roundRect(x, y, barWidth, barH, radius);
          ctx.fill();
        }
        ctx.globalAlpha = 1;
        ctx.globalCompositeOperation = "source-over";
      }

      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [active, color, pulseTracker]);

  return <canvas ref={canvasRef} aria-hidden className={`pointer-events-none ${className}`} />;
}
