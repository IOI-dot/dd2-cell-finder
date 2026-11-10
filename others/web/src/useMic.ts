import { useCallback, useRef, useState } from "react";

const RATE = 16000;
const SPEECH_RMS = 0.012;       // ponytail: fixed level, raise it if a noisy room keeps the mic open
const SILENCE_MS = 1500;        // this long after speech ends the recording
const NOTHING_MS = 8000;        // give up if nobody speaks
const LONGEST_MS = 110000;      // the server takes two minutes

export const WAVE_BARS = 44;
export type MicState = "idle" | "listening" | "transcribing";

/** What actually stopped the microphone, and what to do about it. */
export function micProblem(e: { name?: string; message?: string }) {
  const system = /system/i.test(e.message ?? "");
  if (!window.isSecureContext || !navigator.mediaDevices) return "This address cannot use a microphone. Open the studio at http://127.0.0.1:5173.";
  if (e.name === "NotAllowedError" && system) return "macOS is blocking the microphone for this browser window. Chrome allowed it, but the system refused. Open the studio in your normal Chrome, or turn on the app that started this browser in System Settings, Privacy & Security, Microphone, then restart it.";
  if (e.name === "NotAllowedError") return "Chrome blocked the microphone for this page. Press the icon beside the address, allow the microphone, and reload.";
  if (e.name === "NotFoundError") return "No microphone was found. Connect one and try again.";
  if (e.name === "NotReadableError") return "Another app is holding the microphone, or the system could not start it. Close that app and try again.";
  return `The microphone could not start: ${e.name ?? "unknown error"}${e.message ? `, ${e.message}` : ""}.`;
}

/** 16-bit mono WAV, the one format the server accepts. */
export function wavBytes(chunks: Float32Array[]) {
  const frames = chunks.reduce((n, c) => n + c.length, 0);
  const view = new DataView(new ArrayBuffer(44 + frames * 2));
  const tag = (at: number, s: string) => [...s].forEach((c, i) => view.setUint8(at + i, c.charCodeAt(0)));
  tag(0, "RIFF"); view.setUint32(4, 36 + frames * 2, true); tag(8, "WAVEfmt ");
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, RATE, true); view.setUint32(28, RATE * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  tag(36, "data"); view.setUint32(40, frames * 2, true);
  let at = 44;
  for (const c of chunks) for (const v of c) { view.setInt16(at, Math.max(-1, Math.min(1, v)) * 32767, true); at += 2; }
  return view.buffer;
}

/** Press to speak. Recording ends by itself when you stop, and the text comes back through onText. */
export function useMic(onText: (text: string) => void) {
  const [state, setState] = useState<MicState>("idle");
  const [levels, setLevels] = useState<number[]>([]);
  const [error, setError] = useState("");
  const finish = useRef<((send: boolean) => void) | null>(null);

  const start = useCallback(async () => {
    setError(""); setLevels([]);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    } catch (e) {
      setError(micProblem(e as Error));
      return;
    }
    const ctx = new AudioContext({ sampleRate: RATE });
    const source = ctx.createMediaStreamSource(stream);
    const tap = ctx.createScriptProcessor(1024, 1, 1);   // ponytail: deprecated but one line; an AudioWorklet needs its own module
    const chunks: Float32Array[] = [];
    const began = Date.now();
    let heard = false, quietSince = began;

    const done = async (send: boolean) => {
      finish.current = null;
      tap.disconnect(); source.disconnect();
      stream.getTracks().forEach((t) => t.stop());
      await ctx.close();
      if (!send) { setState("idle"); return; }
      setState("transcribing");
      try {
        const r = await fetch("/api/transcribe", { method: "POST", headers: { "Content-Type": "audio/wav" }, body: wavBytes(chunks) });
        const body = await r.json().catch(() => ({ detail: `the back end answered ${r.status}, so it may not be running` }));
        if (!r.ok) throw new Error(body.detail);
        if (body.text) onText(body.text); else setError("Parakeet heard the recording but found no words in it. Try speaking closer to the microphone.");
      } catch (e) {
        setError(`Transcription failed: ${(e as Error).message}.`);
      }
      setState("idle");
    };

    tap.onaudioprocess = (e) => {
      const d = e.inputBuffer.getChannelData(0);
      chunks.push(new Float32Array(d));
      const rms = Math.sqrt(d.reduce((s, v) => s + v * v, 0) / d.length);
      setLevels((l) => [...l.slice(-(WAVE_BARS - 1)), Math.min(1, rms * 12)]);
      const now = Date.now();
      if (rms > SPEECH_RMS) { heard = true; quietSince = now; }
      if (heard && now - quietSince > SILENCE_MS || now - began > LONGEST_MS) finish.current?.(true);
      else if (!heard && now - began > NOTHING_MS) { setError("I stopped because the microphone picked up no speech. Check which input your system is using."); finish.current?.(false); }
    };
    source.connect(tap);
    tap.connect(ctx.destination);
    finish.current = done;
    setState("listening");
  }, [onText]);

  const toggle = useCallback(() => { if (finish.current) finish.current(true); else if (state === "idle") start(); }, [start, state]);
  const cancel = useCallback(() => finish.current?.(false), []);
  return { state, levels, error, toggle, cancel };
}
