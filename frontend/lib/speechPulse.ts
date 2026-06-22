export interface PulseTracker {
  push: (intensity?: number) => void;
  sample: (now: number) => number;
}

export function createPulseTracker(decayMs = 220): PulseTracker {
  let pulses: { time: number; intensity: number }[] = [];

  return {
    push(intensity = 1) {
      pulses.push({ time: performance.now(), intensity });
      if (pulses.length > 24) pulses = pulses.slice(-24);
    },
    sample(now: number) {
      pulses = pulses.filter((p) => now - p.time < decayMs * 4);
      let sum = 0;
      for (const p of pulses) {
        const age = now - p.time;
        if (age < 0) continue;
        sum += p.intensity * Math.exp(-age / decayMs);
      }
      return Math.min(1, sum);
    },
  };
}
