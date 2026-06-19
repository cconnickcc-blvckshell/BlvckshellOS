"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";

export interface VoiceInputProps {
  disabled?: boolean;
  onTranscript: (text: string) => void;
  onListeningChange?: (listening: boolean, amplitude: number) => void;
  className?: string;
}

export function VoiceInput({
  disabled = false,
  onTranscript,
  onListeningChange,
  className = "",
}: VoiceInputProps) {
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [holdMode, setHoldMode] = useState(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const finalTextRef = useRef("");
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number>(0);
  const amplitudeRef = useRef(0);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const freqDataRef = useRef<Uint8Array | null>(null);

  const drawWaveform = useCallback(() => {
    const canvas = canvasRef.current;
    const analyser = analyserRef.current;
    const data = freqDataRef.current;
    if (!canvas || !analyser || !data) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const barCount = 24;
    const step = Math.floor(data.length / barCount);
    const gap = 3;
    const barWidth = (w - gap * (barCount - 1)) / barCount;

    for (let i = 0; i < barCount; i++) {
      const v = data[i * step] / 255;
      const barH = Math.max(4, v * h * 0.9);
      const x = i * (barWidth + gap);
      const y = (h - barH) / 2;
      ctx.fillStyle = `rgba(168, 85, 247, ${0.35 + v * 0.55})`;
      ctx.fillRect(x, y, barWidth, barH);
    }
  }, []);

  const stopAudio = useCallback(() => {
    cancelAnimationFrame(rafRef.current);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    void audioCtxRef.current?.close();
    audioCtxRef.current = null;
    analyserRef.current = null;
    amplitudeRef.current = 0;
    freqDataRef.current = null;
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext("2d");
      ctx?.clearRect(0, 0, canvas.width, canvas.height);
    }
    onListeningChange?.(false, 0);
  }, [onListeningChange]);

  const startAmplitudeLoop = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyserRef.current = analyser;
      ctx.createMediaStreamSource(stream).connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);
      freqDataRef.current = data;

      const tick = () => {
        analyser.getByteFrequencyData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i++) sum += data[i];
        const amp = sum / data.length / 255;
        amplitudeRef.current = amp;
        onListeningChange?.(true, amp);
        drawWaveform();
        rafRef.current = requestAnimationFrame(tick);
      };
      tick();
    } catch {
      onListeningChange?.(true, 0.3);
    }
  }, [onListeningChange, drawWaveform]);

  const stopRecognition = useCallback(() => {
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    setListening(false);
    setInterim("");
    stopAudio();
  }, [stopAudio]);

  const startRecognition = useCallback(() => {
    const SR =
      typeof window !== "undefined"
        ? window.SpeechRecognition || window.webkitSpeechRecognition
        : undefined;
    if (!SR || disabled) return;

    const recognition = new SR();
    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = true;

    finalTextRef.current = "";

    recognition.onresult = (e: SpeechRecognitionEvent) => {
      let interimText = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalTextRef.current += t;
        else interimText += t;
      }
      setInterim(interimText || finalTextRef.current);
    };

    recognition.onend = () => {
      setListening(false);
      stopAudio();
      const text = (finalTextRef.current || interim).trim();
      setInterim("");
      finalTextRef.current = "";
      if (text) onTranscript(text);
    };

    recognition.onerror = () => stopRecognition();

    recognitionRef.current = recognition;
    setListening(true);
    void startAmplitudeLoop();
    recognition.start();
  }, [disabled, onTranscript, startAmplitudeLoop, stopAudio, stopRecognition]);

  useEffect(() => () => stopRecognition(), [stopRecognition]);

  const isMobile =
    typeof window !== "undefined" && window.matchMedia("(max-width: 768px)").matches;

  return (
    <div className={clsx("flex flex-col items-center gap-3", className)}>
      {interim && (
        <p className="max-w-xs text-center font-body text-sm text-text-secondary">{interim}</p>
      )}

      <button
        type="button"
        disabled={disabled}
        className={clsx(
          "relative flex h-20 w-20 items-center justify-center rounded-full border-2 transition-all",
          listening
            ? "border-error bg-error/20 shadow-lg shadow-error/30 animate-pulse-fast"
            : "border-primary bg-primary/20 hover:border-active hover:bg-primary/30",
          disabled && "opacity-40 cursor-not-allowed",
        )}
        onClick={() => {
          if (isMobile) return;
          if (listening) stopRecognition();
          else startRecognition();
        }}
        onPointerDown={(e) => {
          if (!isMobile) return;
          setHoldMode(true);
          e.preventDefault();
          startRecognition();
        }}
        onPointerUp={() => {
          if (!isMobile || !holdMode) return;
          setHoldMode(false);
          stopRecognition();
        }}
        onPointerLeave={() => {
          if (!isMobile || !holdMode) return;
          setHoldMode(false);
          stopRecognition();
        }}
        aria-label={listening ? "Stop listening" : "Start voice input"}
      >
        <span className="font-mono text-2xl text-text-primary">●</span>
      </button>

      {listening && (
        <canvas
          ref={canvasRef}
          width={200}
          height={40}
          className="h-10 w-[200px] rounded-lg opacity-90"
          aria-hidden
        />
      )}

      <p className="font-mono text-[10px] uppercase tracking-widest text-text-secondary">
        {listening ? "Listening…" : isMobile ? "Hold to speak" : "Tap to speak"}
      </p>
    </div>
  );
}

// Web Speech API types (browser)
interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((ev: SpeechRecognitionEvent) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
}

interface SpeechRecognitionEvent {
  resultIndex: number;
  results: { length: number; [i: number]: { isFinal: boolean; 0: { transcript: string } } };
}

declare global {
  interface Window {
    SpeechRecognition: new () => SpeechRecognition;
    webkitSpeechRecognition: new () => SpeechRecognition;
  }
}
