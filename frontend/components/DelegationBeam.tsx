"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

export interface DelegationBeamProps {
  active: boolean;
  fromRef: React.RefObject<HTMLElement | null>;
  toBrainId?: string;
  brainOrbRefs: React.MutableRefObject<Map<string, HTMLElement>>;
  containerRef: React.RefObject<HTMLElement | null>;
}

interface BeamCoords {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export function DelegationBeam({
  active,
  fromRef,
  toBrainId,
  brainOrbRefs,
  containerRef,
}: DelegationBeamProps) {
  const [coords, setCoords] = useState<BeamCoords | null>(null);

  useEffect(() => {
    if (!active || !toBrainId) {
      setCoords(null);
      return;
    }

    function measure() {
      if (!toBrainId) {
        setCoords(null);
        return;
      }
      const container = containerRef.current;
      const from = fromRef.current;
      const to = brainOrbRefs.current.get(toBrainId);
      if (!container || !from || !to) {
        setCoords(null);
        return;
      }
      const cRect = container.getBoundingClientRect();
      const fRect = from.getBoundingClientRect();
      const tRect = to.getBoundingClientRect();
      setCoords({
        x1: fRect.left + fRect.width / 2 - cRect.left,
        y1: fRect.top + fRect.height / 2 - cRect.top,
        x2: tRect.left + tRect.width / 2 - cRect.left,
        y2: tRect.top + tRect.height / 2 - cRect.top,
      });
    }

    measure();
    const id = window.setInterval(measure, 50);
    window.addEventListener("resize", measure);
    return () => {
      clearInterval(id);
      window.removeEventListener("resize", measure);
    };
  }, [active, toBrainId, fromRef, brainOrbRefs, containerRef]);

  if (!coords) return null;

  const midX = (coords.x1 + coords.x2) / 2;
  const path = `M ${coords.x1} ${coords.y1} Q ${midX} ${coords.y1} ${coords.x2} ${coords.y2}`;

  return (
    <AnimatePresence>
      {active && (
        <motion.svg
          className="pointer-events-none absolute inset-0 z-20 h-full w-full overflow-visible"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
        >
          <defs>
            <filter id="beam-glow">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <motion.path
            d={path}
            fill="none"
            stroke="#22D3EE"
            strokeWidth="2"
            strokeOpacity="0.7"
            filter="url(#beam-glow)"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1, strokeOpacity: [0.4, 0.9, 0.4] }}
            transition={{
              pathLength: { duration: 0.35, ease: "easeOut" },
              strokeOpacity: { repeat: Infinity, duration: 0.8 },
            }}
          />
          <motion.circle
            cx={coords.x2}
            cy={coords.y2}
            r="6"
            fill="#A855F7"
            initial={{ scale: 0 }}
            animate={{ scale: [1, 1.4, 1], opacity: [0.6, 1, 0.6] }}
            transition={{ repeat: Infinity, duration: 0.6 }}
          />
        </motion.svg>
      )}
    </AnimatePresence>
  );
}
