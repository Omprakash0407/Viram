"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bot, Loader2, MessageCircle, Mic, Send, Volume2, VolumeX, X } from "lucide-react";
import { aiApi, geoApi, tripsApi, type TripCreatePayload, type TripDetail, type ItineraryDayRow, type ItineraryItemRow } from "@/lib/api";
import { useSession } from "@/lib/session";
import { INDIA_STATES, stateHref } from "../explore/states";

/**
 * Rule-based trip-planning assistant (the chat counterpart of the /plan
 * wizard). Like RuleBasedRecommendationEngine, the conversation engine is a
 * deterministic, replaceable component — a future LLM backend can drive the
 * same message contract. It asks for the basic needs one at a time
 * (destination → dates → party → budget → moods), shows its understanding,
 * then creates a real trip + recommendations + itinerary via the API.
 */

type Msg = {
  from: "bot" | "user";
  ai?: boolean;
  text: string;
  chips?: string[];
};

type Draft = {
  cityId: string | null;
  cityName: string | null;
  startsOn: string | null;
  endsOn: string | null;
  partySize: number | null;
  budgetTier: string | null;
  moods: string[];
};

const EMPTY: Draft = {
  cityId: null, cityName: null, startsOn: null, endsOn: null,
  partySize: null, budgetTier: null, moods: [],
};

/** Signed-out confirm: the draft waits in sessionStorage across the login redirect. */
const DRAFT_KEY = "viram.chat.tripDraft";

/** Speak-aloud preference (beta) persists across sessions. */
const SPEAK_KEY = "viram.chat.speakAloud";

/** Voice language choice (beta): "auto" or a specific language code. */
const LANG_KEY = "viram.chat.voiceLang";

/**
 * Languages offered for voice (beta). India-first set: English + the major
 * Indic scripts a traveller is most likely to use, each matched by script
 * for detection and speak-aloud voice selection.
 */
const VOICE_LANGS = [
  { code: "en-IN", label: "English" },
  { code: "hi-IN", label: "हिन्दी" },
  { code: "or-IN", label: "ଓଡ଼ିଆ" },
  { code: "bn-IN", label: "বাংলা" },
  { code: "ta-IN", label: "தமிழ்" },
  { code: "te-IN", label: "తెలుగు" },
] as const;

/** Unicode script → language code (for auto-detection and speech output). */
const SCRIPT_LANGS: Array<[RegExp, string]> = [
  [/[\u0980-\u09FF]/, "bn-IN"], // Bengali
  [/[\u0B00-\u0B7F]/, "or-IN"], // Odia
  [/[\u0B80-\u0BFF]/, "ta-IN"], // Tamil
  [/[\u0C00-\u0C7F]/, "te-IN"], // Telugu
  [/[\u0900-\u097F]/, "hi-IN"], // Devanagari (Hindi et al.)
];

/** Best-effort language detection from text. Latin script → null (unknown). */
function detectLang(text: string): string | null {
  for (const [re, code] of SCRIPT_LANGS) if (re.test(text)) return code;
  return null;
}

function langLabel(code: string): string {
  if (code === "auto") return "Auto";
  return VOICE_LANGS.find((l) => l.code === code)?.label ?? code;
}

/** Pick the best installed speech-synthesis voice for a language. */
function pickVoice(lang: string): SpeechSynthesisVoice | null {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  const norm = (l: string) => l.replace("_", "-");
  const base = lang.split("-")[0];
  return (
    voices.find((v) => norm(v.lang) === lang) ??
    voices.find((v) => norm(v.lang).startsWith(base)) ??
    null
  );
}

/**
 * Web Speech API (voice beta) — a free, on-device browser capability: no API
 * key, no cloud vendor lock-in. Mic input transcribes into the composer and
 * sends; speaker mode reads Vira's replies aloud. Both features degrade
 * honestly (button hidden / inline message) when the browser lacks support.
 */
type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  continuous: boolean;
  start(): void;
  stop(): void;
  onresult:
    | ((e: {
        resultIndex: number;
        results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal?: boolean }> & { length: number };
      }) => void)
    | null;
  onerror: ((e: { error?: string }) => void) | null;
  onend: (() => void) | null;
};
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function speechCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

function saveDraft(d: Draft) {
  try {
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify(d));
  } catch {
    /* private mode etc. — the user just answers again after login */
  }
}

function loadDraft(): Draft | null {
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY);
    if (!raw) return null;
    const d = JSON.parse(raw) as Draft;
    return d && typeof d.cityId === "string" && typeof d.startsOn === "string" ? d : null;
  } catch {
    return null;
  }
}

function clearDraft() {
  try {
    sessionStorage.removeItem(DRAFT_KEY);
  } catch {
    /* ignore */
  }
}

/** "Ask Vira" entry popup: shown once per browser session, then remembered. */
const TEASER_KEY = "viram.chat.teaserDismissed";

function teaserDismissed(): boolean {
  try {
    return sessionStorage.getItem(TEASER_KEY) === "1";
  } catch {
    return true; // storage unavailable → stay quiet rather than nag
  }
}

function markTeaserDismissed() {
  try {
    sessionStorage.setItem(TEASER_KEY, "1");
  } catch {
    /* ignore */
  }
}

const MOOD_LABELS: Record<string, string> = {
  NATURE_RELAXATION: "Nature & Relaxation",
  CITY_LIFE: "City Life",
  ADVENTURE_THRILL: "Adventure & Thrill",
  FOOD_CULTURE: "Food & Culture",
};

const BUDGETS = ["Budget", "Moderate", "Premium", "Executive"];

/** States suggested per travel mood. Odisha always included — it's the live one. */
const MOOD_STATES: Record<string, string[]> = {
  NATURE_RELAXATION: ["Kerala", "Himachal Pradesh", "Uttarakhand", "Odisha"],
  CITY_LIFE: ["Delhi", "Maharashtra", "Karnataka", "Telangana", "Odisha"],
  ADVENTURE_THRILL: ["Himachal Pradesh", "Uttarakhand", "Sikkim", "Ladakh", "Odisha"],
  FOOD_CULTURE: ["West Bengal", "Tamil Nadu", "Punjab", "Rajasthan", "Odisha"],
};

type Step =
  | "firsttime" | "dmood" | "states"
  | "city" | "dates" | "party" | "budget" | "moods" | "confirm" | "done" | "edit";

/** Shared mood keyword parsing (discovery flow and trip flow use the same grammar). */
function parseMoods(text: string): string[] {
  const q = text.toLowerCase();
  const picked: string[] = [];
  if (q.includes("nature") || q.includes("relax")) picked.push("NATURE_RELAXATION");
  if (q.includes("city")) picked.push("CITY_LIFE");
  if (q.includes("adventure") || q.includes("thrill") || q.includes("trek")) picked.push("ADVENTURE_THRILL");
  if (q.includes("food") || q.includes("culture")) picked.push("FOOD_CULTURE");
  return picked;
}

function iso(d: Date): string {
  // Local-date ISO string. (toISOString() would shift a local midnight back a
  // day west-of-UTC timezones — e.g. IST — silently shortening trips.)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const NUM_WORDS: Record<string, number> = {
  one: 1, two: 2, three: 3, four: 4, five: 5,
  six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
};

type ChatWeather = {
  city: { name: string };
  date: string;
  temperature_c: number;
  condition: string;
  tmax_c: number | null;
  tmin_c: number | null;
  retrieved_at: string;
  cached: boolean;
};

/** Live forecast via the existing intelligence endpoint (§27). Returns null with
 *  `unavailable` telling transient provider failure apart from "beyond the
 *  forecast horizon" — the caller words the fallback honestly. Never fatal. */
async function getWeather(
  cityId: string,
  date?: string,
): Promise<{ w: ChatWeather | null; unavailable: boolean }> {
  try {
    const qs = new URLSearchParams({ city_id: cityId });
    if (date) qs.set("date", date);
    const res = await fetch(`/api/v1/intelligence/weather?${qs.toString()}`);
    if (res.status === 503) return { w: null, unavailable: true };
    if (!res.ok) return { w: null, unavailable: false };
    return { w: (await res.json()) as ChatWeather, unavailable: false };
  } catch {
    return { w: null, unavailable: true };
  }
}

function weatherFallback(dateIso: string, unavailable: boolean): string {
  return unavailable
    ? `(The weather provider isn't responding right now — ask me again in a moment.)`
    : `(No forecast yet for ${fmtDate(dateIso)} — providers only look about two weeks ahead. Ask me again closer to your trip.)`;
}

function weatherLine(w: ChatWeather): string {
  const temps =
    w.tmax_c != null && w.tmin_c != null
      ? `, high ${Math.round(w.tmax_c)}°/low ${Math.round(w.tmin_c)}°`
      : "";
  return `${Math.round(w.temperature_c)}°C, ${w.condition.toLowerCase()}${temps} · ${
    w.cached ? "cached snapshot" : "fresh from provider"
  }`;
}

function fmtDate(isoStr: string): string {
  return new Date(isoStr + "T00:00:00").toLocaleDateString("en-IN", {
    day: "numeric", month: "short", year: "numeric",
  });
}

/** Parse loose date text: "12 oct", "2026-10-12", "12/10" (DD/MM). */
function parseDate(text: string): string | null {
  const t = text.trim().toLowerCase();
  let m = t.match(/(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (m) return `${m[1]}-${m[2].padStart(2, "0")}-${m[3].padStart(2, "0")}`;
  m = t.match(/(\d{1,2})[\/.\-](\d{1,2})(?:[\/.\-](\d{2,4}))?/);
  if (m) {
    const year = m[3]
      ? (m[3].length === 2 ? 2000 + parseInt(m[3], 10) : parseInt(m[3], 10))
      : new Date().getFullYear();
    const day = parseInt(m[1], 10);
    const month = parseInt(m[2], 10);
    if (month >= 1 && month <= 12 && day >= 1 && day <= 31) {
      return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    }
  }
  const months = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"];
  m = t.match(/(\d{1,2})\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*/);
  if (m) {
    const day = parseInt(m[1], 10);
    const month = months.indexOf(m[2]) + 1;
    if (day >= 1 && day <= 31) {
      return `${new Date().getFullYear()}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    }
  }
  return null;
}

function parseParty(text: string): number | null {
  const m = text.match(/\b(\d{1,2})\b/);
  const n = m ? parseInt(m[1], 10) : null;
  if (n && n >= 1 && n <= 50) return n;
  if (/\b(solo|alone|just me|myself)\b/i.test(text)) return 1;
  if (/\b(couple|honeymoon|two of us|wife|husband|partner)\b/i.test(text)) return 2;
  if (/\b(family|group|friends)\b/i.test(text)) return 4;
  return null;
}

export default function ChatAssistant() {
  const { user } = useSession();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState<Step>("firsttime");
  const [suggestMoods, setSuggestMoods] = useState<string[]>([]);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [created, setCreated] = useState<{ tripId: string } | null>(null);
  const [editTrip, setEditTrip] = useState<TripDetail | null>(null);
  const [datePick, setDatePick] = useState<{ start: string; end: string }>({ start: "", end: "" });
  const [teaser, setTeaser] = useState(false);
  const [aiMode, setAiMode] = useState(false);
  const [aiHistory, setAiHistory] = useState<Array<{ role: string; text: string }>>([]);
  const [cities, setCities] = useState<Array<{ id: string; name: string; slug: string }>>([]);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [speakOn, setSpeakOn] = useState(false);
  const [voiceLang, setVoiceLang] = useState<string>("auto");
  const [micHint, setMicHint] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const spokenIdxRef = useRef(-1);
  // Last language that produced usable speech (auto mode orders candidates
  // with it first). A ref, not state — the visible Auto choice is never
  // silently downgraded to a fixed language.
  const lastWorkedRef = useRef<string | null>(null);

  useEffect(() => {
    geoApi.cities().then((r) => setCities(r.items)).catch(() => {});
  }, []);

  // Site-entry greeting: pop the "Ask Vira" welcome shortly after the visitor
  // lands, once per session. Skipped entirely when a saved draft will resume
  // the conversation by itself (the login handoff already greets them).
  useEffect(() => {
    if (teaserDismissed()) return;
    const t = setTimeout(() => {
      if (!loadDraft()) setTeaser(true);
    }, 1200);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [msgs, busy]);

  // Voice support is browser-dependent — detect client-side only (SSR-safe)
  // and restore the speak-aloud preference.
  useEffect(() => {
    setVoiceSupported(Boolean(speechCtor()));
    try {
      if (localStorage.getItem(SPEAK_KEY) === "1") setSpeakOn(true);
      const saved = localStorage.getItem(LANG_KEY);
      if (saved) setVoiceLang(saved);
    } catch {
      /* private mode — defaults */
    }
  }, []);

  // "Auto" mode still needs a concrete code for the recogniser at start time:
  // the language that last worked (this session) + English + browser UI
  // language, deduplicated.
  function recognitionLangs(): string[] {
    const nav = typeof navigator !== "undefined" ? navigator.language : "en-IN";
    const set = [
      voiceLang !== "auto" ? voiceLang : null,
      voiceLang === "auto" ? lastWorkedRef.current : null,
      "en-IN",
      nav,
    ].filter((l): l is string => Boolean(l));
    return [...new Set(set)];
  } // Speak each NEW bot reply aloud when speaker mode is on (beta).
  // spokenIdxRef makes it one-shot per message — re-renders never re-speak.
  useEffect(() => {
    if (!speakOn || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const last = msgs[msgs.length - 1];
    if (!last || last.from !== "bot" || spokenIdxRef.current >= msgs.length - 1) return;
    spokenIdxRef.current = msgs.length - 1;
    // Voice language for OUTPUT: match the message's script first (always
    // the most accurate signal), then honour a fixed override, then defaults.
    const lang =
      detectLang(last.text) ??
      (voiceLang !== "auto" ? voiceLang : null) ??
      recognitionLangs()[0] ??
      "en-IN";
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(last.text
          .replace(/β/g, " beta ")
          .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}]/gu, "")
          .replace(/\s+/g, " ")
          .trim(),
      );
      u.lang = lang;
      const v = pickVoice(lang);
      if (v) u.voice = v;
      u.rate = 1;
      window.speechSynthesis.speak(u);
    } catch {
      /* speech unavailable — text chat still works */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [msgs, speakOn, voiceLang]);

  // Unmount: never leave a recognizer or a speaking utterance running.
  useEffect(
    () => () => {
      try {
        recognitionRef.current?.stop();
      } catch {
        /* already stopped */
      }
      try {
        window.speechSynthesis?.cancel();
      } catch {
        /* unsupported */
      }
    },
    [],
  );

  // Login handoff: the chat is layout-mounted, so it survives the redirect —
  // when a saved draft exists and the session just became signed-in, resume
  // the conversation at confirm without waiting for the user to re-open it.
  const draftResumeRef = useRef(false);
  useEffect(() => {
    if (!user || draftResumeRef.current) return;
    const saved = loadDraft();
    if (!saved) return;
    draftResumeRef.current = true;
    clearDraft();
    setDraft(saved);
    setOpen(true);
    setMsgs([
      {
        from: "bot",
        text: `Welcome back, ${user.display_name}! I kept your plan: ${saved.cityName}, ${fmtDate(saved.startsOn!)} → ${fmtDate(saved.endsOn!)}, ${saved.partySize} traveller${saved.partySize === 1 ? "" : "s"}, ${saved.budgetTier?.toLowerCase()} budget, ${saved.moods.map((m) => MOOD_LABELS[m]).join(" + ").toLowerCase()}. Shall I build it?`,
        chips: ["Yes, build it", "Start over"],
      },
    ]);
    setStep("confirm");
  }, [user]);

  function say(text: string, chips?: string[]) {
    setMsgs((m) => [...m, { from: "bot", text, chips }]);
  }
  function reply(text: string) {
    setMsgs((m) => [...m, { from: "user", text }]);
  }

  /** Dictate into the composer; the final transcript auto-sends (beta).
   * "Auto" language: the recogniser is script-locked per attempt, so we try
   * candidate languages in turn (fixed pick → English → browser language);
   * the first attempt that returns usable speech wins and is remembered so
   * the next tap starts with the language that actually worked. */
  function startListening() {
    const Ctor = speechCtor();
    if (!Ctor || busy) return;
    stopListening();
    const candidates = recognitionLangs();
    let attempt = 0;

    const runAttempt = () => {
      if (attempt >= candidates.length) {
        setListening(false);
        say("🎙 Voice (beta): I couldn't hear a language I recognise — try picking one from the language button, or type your answer.");
        return;
      }
      const lang = candidates[attempt];
      const rec = new Ctor();
      rec.lang = lang;
      rec.interimResults = true;
      rec.maxAlternatives = 1;
      rec.continuous = false;
      let finalText = "";
      let gotUsable = false;
      let aborted = false;
      rec.onresult = (e) => {
        let interim = "";
        for (let i = e.resultIndex; i < e.results.length; i += 1) {
          const r = e.results[i];
          const t = r[0]?.transcript ?? "";
          if (r.isFinal) {
            finalText += t;
            if (t.trim()) gotUsable = true;
          } else {
            interim += t;
            if (t.trim()) gotUsable = true;
            const detected = detectLang(interim + finalText);
            if (detected && detected !== lang && !aborted) {
              // Wrong script-lock: stop; onend retries in the detected language.
              aborted = true;
              try { rec.stop(); } catch { /* stopping */ }
            }
          }
        }
        if (finalText || interim) setInput((finalText + interim).trim());
      };
      rec.onerror = (e) => {
        recognitionRef.current = null;
        if (e.error === "no-speech" && attempt < candidates.length - 1) {
          attempt += 1;
          runAttempt(); // auto mode: try the next candidate language
          return;
        }
        setListening(false);
        const reason =
          e.error === "not-allowed" || e.error === "service-not-allowed"
            ? "Microphone access was blocked — allow it in your browser's address bar and try again."
            : e.error === "no-speech"
              ? "I didn't hear anything — try again a bit closer to the mic."
              : e.error === "network"
                ? "Speech recognition needs a network connection — your words stayed on this device."
                : "Voice input failed — you can still type your answer.";
        say(`🎙 Voice (beta): ${reason}`);
      };
      rec.onend = () => {
        recognitionRef.current = null;
        const text = finalText.trim();
        if (aborted) {
          // Script-detected mid-utterance: retry locked onto that language.
          // No text captured → advance instead, so a silent abort can't loop.
          const target = text ? detectLang(text) : null;
          if (target) candidates[attempt] = target;
          else if (attempt < candidates.length - 1) attempt += 1;
          runAttempt();
          return;
        }
        if (text) {
          setListening(false);
          if (voiceLang === "auto") {
            lastWorkedRef.current = detectLang(text) ?? lang; // order next attempt
          }
          void send(text); // final transcript auto-sends, like a typed answer
          return;
        }
        if (!gotUsable && attempt < candidates.length - 1) {
          attempt += 1;
          runAttempt();
        } else {
          setListening(false);
        }
      };
      recognitionRef.current = rec;
      try {
        rec.start();
      } catch {
        recognitionRef.current = null;
        setListening(false);
        say("🎙 Voice (beta): couldn't start the microphone — try again.");
      }
    };

    setListening(true);
    setMicHint(
      voiceLang === "auto"
        ? `Listening — speak ${candidates.map(langLabel).join(" or ")}`
        : `Listening — ${langLabel(voiceLang)}`,
    );
    runAttempt();
  }

  function stopListening() {
    try {
      recognitionRef.current?.stop();
    } catch {
      /* already stopped */
    }
    recognitionRef.current = null;
    setListening(false);
  }

  function toggleSpeak() {
    const next = !speakOn;
    setSpeakOn(next);
    try {
      localStorage.setItem(SPEAK_KEY, next ? "1" : "0");
    } catch {
      /* private mode — session-only */
    }
    if (!next) {
      try {
        window.speechSynthesis?.cancel();
      } catch {
        /* unsupported */
      }
    } else {
      spokenIdxRef.current = msgs.length - 1; // don't re-read history
      say("🔊 Speaker on (beta) — I'll read my replies aloud, matching your language.");
    }
  }

  /** Manual language override (beta voice). "auto" re-enables detection. */
  function setVoiceLangManual(code: string) {
    setVoiceLang(code);
    try {
      localStorage.setItem(LANG_KEY, code);
    } catch {
      /* private mode — session-only */
    }
    if (listening) stopListening();
    say(
      code === "auto"
        ? "🎙 Language: Auto — speak in any of my supported languages and I'll follow."
        : `🎙 Language set to ${langLabel(code)}.`,
    );
  }

  function dismissTeaser() {
    setTeaser(false);
    markTeaserDismissed();
  }

  function begin() {
    setOpen(true);
    dismissTeaser();
    if (msgs.length === 0) {
      // Returning from the login handoff: resume where the visitor left off.
      const saved = user ? loadDraft() : null;
      if (saved) {
        clearDraft();
        setDraft(saved);
        say(
          `Welcome back, ${user!.display_name}! I kept your plan: ${saved.cityName}, ${fmtDate(saved.startsOn!)} → ${fmtDate(saved.endsOn!)}, ${saved.partySize} traveller${saved.partySize === 1 ? "" : "s"}, ${saved.budgetTier?.toLowerCase()} budget, ${saved.moods.map((m) => MOOD_LABELS[m]).join(" + ").toLowerCase()}. Shall I build it?`,
          ["Yes, build it", "Start over"],
        );
        setStep("confirm");
        return;
      }
      say(
        user
          ? `Hi ${user.display_name}! I'm Vira, your trip assistant. First things first — is this your first time visiting India?`
          : "Hi! I'm Vira, your trip assistant. First things first — is this your first time visiting India?",
        ["Yes, first time", "No, I've been before"],
      );
    }
  }

  /** Discovery flow: first-time → mood → state suggestions → redirect. */
  async function handleFirstTime(text: string): Promise<Step> {
    if (/first|yes|new|never/i.test(text)) {
      say("Welcome! A first trip to India is special. What's your travelling mood — what kind of experience are you after?", Object.values(MOOD_LABELS));
      return "dmood";
    }
    if (/no|been|before|visited/i.test(text)) {
      say("Great, a returning traveller! Where in India do you want to go this time?", cities.slice(0, 6).map((c) => c.name));
      return "city";
    }
    say("Just so I point you the right way — is this your first time visiting India?", ["Yes, first time", "No, I've been before"]);
    return "firsttime";
  }

  async function handleDiscoverMood(text: string): Promise<Step> {
    const picked = parseMoods(text);
    if (picked.length === 0) {
      say("Try naming a mood — for example \"nature\" or \"food and culture\".", Object.values(MOOD_LABELS));
      return "dmood";
    }
    setSuggestMoods(picked);
    const states = [...new Set(picked.flatMap((m) => MOOD_STATES[m] ?? []))];
    const chips = states.map((s) => (s === "Odisha" ? "Odisha (live now)" : s));
    say(
      `Based on ${picked.map((m) => MOOD_LABELS[m]).join(" + ").toLowerCase()}, these states fit best — pick one and I'll take you to its page:`,
      chips,
    );
    return "states";
  }

  async function handleStates(text: string): Promise<Step> {
    const q = text.toLowerCase();
    if (/another|other|different|change/i.test(text) && !q.includes("odisha")) {
      say("Sure — which mood should I suggest from this time?", Object.values(MOOD_LABELS));
      return "dmood";
    }
    const hit = INDIA_STATES.find((s) => q.includes(s.name.toLowerCase()));
    if (!hit) {
      const states = [...new Set(suggestMoods.flatMap((m) => MOOD_STATES[m] ?? []))];
      say("I didn't catch the state — pick one of these:", states.map((s) => (s === "Odisha" ? "Odisha (live now)" : s)));
      return "states";
    }
    if (hit.slug === "odisha") {
      say("Taking you to Odisha — explore its cities, places and culture.");
      setOpen(false);
      setMsgs([]);
      setDraft(EMPTY);
      setCreated(null);
      router.push(stateHref("odisha"));
      return "firsttime";
    }
    // Design rule 8: never pretend unverified content exists. Other states
    // have no seeded data yet, so their pages would 404 — say so honestly.
    say(`${hit.name} is on our roadmap — verified content for it is coming soon, and I won't send you to an empty page. Odisha is live right now — want to start there?`, ["Odisha (live now)", "Pick another state"]);
    return "states";
  }

  /** Trip-building flow (returning travellers). */
  async function handleCity(text: string): Promise<Step> {
    const q = text.toLowerCase();
    const hit =
      cities.find((c) => q.includes(c.name.toLowerCase())) ??
      cities.find((c) => q.includes(c.slug.split("-")[0]));
    if (!hit) {
      say("I don't have that city in my catalogue yet — for now I can plan Odisha. Try Puri, Konark, Bhubaneswar, Daringbadi or Chilika.");
      return "city";
    }
    setDraft((d) => ({ ...d, cityId: hit.id, cityName: hit.name }));
    say(`Great — ${hit.name} it is. When do you want to travel? You can say just the start date (I'll suggest a 3-day trip) or both dates, like "12 Oct to 14 Oct".`);
    return "dates";
  }

  async function handleDates(text: string): Promise<Step> {
    const range = text.split(/\s+(?:to|till|until|through|-|–|—)\s+/i);
    const start = parseDate(range[0] ?? "");
    if (!start) {
      say("I couldn't read that date. Try something like \"12 Oct\" or \"2026-10-12\".");
      return "dates";
    }
    let end = range[1] ? parseDate(range[1]) : null;
    if (!end) {
      const d = new Date(start + "T00:00:00");
      d.setDate(d.getDate() + 2);
      end = iso(d);
      say(`I'll plan 3 days from ${fmtDate(start)} — tell me if you'd like different dates later.`);
    }
    if (new Date(end) < new Date(start)) {
      say("The end date looks before the start date — give me the dates again?");
      return "dates";
    }
    setDraft((d) => ({ ...d, startsOn: start, endsOn: end }));
    say(`Got it: ${fmtDate(start)} to ${fmtDate(end)}. How many travellers?`, ["1", "2", "4"]);
    return "party";
  }

  async function handleParty(text: string): Promise<Step> {
    const n = parseParty(text);
    if (!n) {
      say("How many people are travelling? A number works best (1–50).", ["1", "2", "4"]);
      return "party";
    }
    setDraft((d) => ({ ...d, partySize: n }));
    say(`${n} traveller${n === 1 ? "" : "s"}. What's your budget per person?`, BUDGETS);
    return "budget";
  }

  async function handleBudget(text: string): Promise<Step> {
    const q = text.toLowerCase();
    if (/no|skip|none|not sure|don'?t know|later/i.test(q)) {
      say("No worries — I'll use a moderate budget. And what's your travel style? You can pick more than one.", Object.values(MOOD_LABELS));
      setDraft((d) => ({ ...d, budgetTier: "MODERATE" }));
      return "moods";
    }
    const hit = BUDGETS.find((b) => q.includes(b.toLowerCase()));
    if (!hit) {
      say("Pick one of these budget levels — or say \"no\" and I'll use moderate:", BUDGETS);
      return "budget";
    }
    setDraft((d) => ({ ...d, budgetTier: hit.toUpperCase() }));
    say("And what's your travel style? You can pick more than one — just list them.", Object.values(MOOD_LABELS));
    return "moods";
  }

  async function handleMoods(text: string): Promise<Step> {
    const picked = parseMoods(text);
    if (picked.length === 0) {
      say("Try naming a style — for example \"nature\" or \"food and culture\".", Object.values(MOOD_LABELS));
      return "moods";
    }
    const next = { ...draft, moods: picked };
    setDraft(next);
    say(
      `Here's what I have:\n• Destination: ${next.cityName}\n• Dates: ${fmtDate(next.startsOn!)} → ${fmtDate(next.endsOn!)}\n• Travellers: ${next.partySize}\n• Budget: ${next.budgetTier}\n• Style: ${picked.map((m) => MOOD_LABELS[m]).join(", ")}\n\nShall I build your plan?`,
      ["Yes, build it", "Start over"],
    );
    return "confirm";
  }

  async function handleConfirm(text: string): Promise<Step> {
    if (/start over|no|change|wrong/i.test(text)) {
      setDraft(EMPTY);
      setCreated(null);
      clearDraft();
      say("No problem — let's start fresh. Is this your first time visiting India?", ["Yes, first time", "No, I've been before"]);
      return "firsttime";
    }
    if (/sign/i.test(text)) {
      // Hand off to sign-in; the draft is already saved and the ?next= target
      // brings the visitor back to this page, where the chat resumes it.
      const here = window.location.pathname + window.location.search;
      router.push(`/login?next=${encodeURIComponent(here)}`);
      return "confirm";
    }
    if (!/yes|build|go ahead|sure|ok|do it|create/i.test(text)) {
      say("Just confirm — shall I build the plan?", ["Yes, build it", "Start over"]);
      return "confirm";
    }
    if (!user) {
      // Keep everything the visitor told me, then send them to sign in.
      saveDraft(draft);
      say(
        "I have your whole plan — I just need an account to save it to. Sign in (or register) and I'll pick up exactly where we left off.",
        ["Sign in to save this plan"],
      );
      return "confirm";
    }
    setBusy(true);
    try {
      const payload: TripCreatePayload = {
        city_id: draft.cityId!,
        starts_on: draft.startsOn!,
        ends_on: draft.endsOn!,
        party_size: draft.partySize!,
        moods: draft.moods,
        budget_tier: draft.budgetTier!,
      };
      const trip = await tripsApi.create(payload);
      const rec = await tripsApi.recommendations(trip.id, true);
      if (rec.run_id && rec.items.length > 0) {
        await tripsApi.accept(trip.id, rec.run_id, []);
        await tripsApi.generateItinerary(trip.id, rec.run_id);
      } else {
        await tripsApi.generateItinerary(trip.id, null);
      }
      setCreated({ tripId: trip.id });
      const detail = await tripsApi.detail(trip.id);
      setEditTrip(detail);
      const itemCount = detail.itinerary?.days.reduce((n, d) => n + d.items.length, 0) ?? 0;
      // Done-state weather: the trip's start-date forecast, inline (§27).
      // Provider failure (e.g. date beyond the forecast horizon) degrades to
      // an honest note, never an error.
      const { w, unavailable } = await getWeather(draft.cityId!, draft.startsOn!);
      const weatherText = w
        ? `\n\nForecast for ${fmtDate(w.date)}: ${weatherLine(w)}`
        : `\n\n${weatherFallback(draft.startsOn!, unavailable)}`;
      say(
        `Done! Your ${draft.cityName} journey is ready: ${fmtDate(draft.startsOn!)} → ${fmtDate(draft.endsOn!)}, with ${itemCount} experience${itemCount === 1 ? "" : "s"} across ${detail.itinerary?.days.length ?? 0} day${detail.itinerary?.days.length === 1 ? "" : "s"}.${weatherText}\n\nWant any changes? Say things like "remove <place>" or "add one more day" — or just tell me what to adjust.`,
        ["Open my trip", "Plan another", "Show my itinerary"],
      );
      return "edit";
    } catch (err) {
      say(err instanceof Error ? `Something went wrong: ${err.message}` : "Something went wrong creating the trip.");
      return "confirm";
    } finally {
      setBusy(false);
    }
  }

  /** Post-build editing: "remove X", "add one more day", "show my itinerary". */
  function itinerarySummary(t: TripDetail): string {
    const days = t.itinerary?.days ?? [];
    if (days.length === 0) return "(no itinerary yet)";
    return days
      .map((d) => `Day ${d.day_number}: ${(d.items.map((i) => i.title).join(", ") || "free day")}`)
      .join("\n");
  }

  async function handleEdit(text: string): Promise<Step> {
    const t = editTrip;
    if (!t) return "done";
    const q = text.toLowerCase();

    if (/open|my trip|dashboard/i.test(text)) {
      router.push("/trips");
      setOpen(false);
      return "edit";
    }
    if (/another|new trip|start over/i.test(text)) {
      setDraft(EMPTY);
      setCreated(null);
      setEditTrip(null);
      clearDraft();
      say("Let's plan another one. Is this your first time visiting India?", ["Yes, first time", "No, I've been before"]);
      return "firsttime";
    }

    const showMatch = q.match(/show|what.*plan|itinerary|summary/);
    if (showMatch && !/remove|add/.test(q)) {
      say(`Here's your ${t.city?.name ?? ""} plan:\n${itinerarySummary(t)}`, ["Open my trip", "Plan another"]);
      return "edit";
    }

    // "what's the weather" / "will it rain" — forecast for the trip start
    if (/weather|forecast|rain|temperature|hot|cold/.test(q) && !/remove|add/.test(q)) {
      setBusy(true);
      try {
        const { w, unavailable } = t.city
          ? await getWeather(t.city.id, t.starts_on)
          : { w: null, unavailable: false };
        say(
          w
            ? `Forecast for ${t.city?.name ?? "your trip"} on ${fmtDate(w.date)}: ${weatherLine(w)}`
            : weatherFallback(t.starts_on, unavailable),
          ["Show my itinerary", "Open my trip"],
        );
      } finally {
        setBusy(false);
      }
      return "edit";
    }

    // "add one more day" / "add 2 days" / "extend by three days"
    const addDay = q.match(/add\s+(?:(\d{1,2})|(?:(one|two|three|four|five|six|seven|eight|nine|ten)\s+)?)(?:more\s+)?day/)
      ?? q.match(/extend(?:\s+by)?\s+(?:(\d{1,2})|(one|two|three|four|five|six|seven|eight|nine|ten))\s+day/);
    const addDayRaw = addDay ? (addDay[1] ?? addDay[2]) : null;
    if (addDayRaw) {
      const n = /\d/.test(addDayRaw) ? parseInt(addDayRaw, 10) : NUM_WORDS[addDayRaw] ?? 0;
      if (n < 1 || n > 30) {
        say("How many days should I add? (1–30 works best.)");
        return "edit";
      }
      setBusy(true);
      try {
        await tripsApi.extend(t.id, n);
        const fresh = await tripsApi.detail(t.id);
        setEditTrip(fresh);
        const days = fresh.itinerary?.days ?? [];
        say(
          `Extended! You now travel ${fmtDate(fresh.starts_on)} → ${fmtDate(fresh.ends_on)} (${days.length} days). The new day${n === 1 ? " is" : "s are"} open — want me to add something specific, like a café or a rest morning?`,
          ["Show my itinerary", "Open my trip"],
        );
        return "edit";
      } catch (err) {
        say(err instanceof Error ? `Couldn't extend: ${err.message}` : "Couldn't extend the trip.");
        return "edit";
      } finally {
        setBusy(false);
      }
    }

    // "remove Raghurajpur" / "drop Jagannath Temple" / "delete day 2 item X"
    const removeMatch = q.match(/(?:remove|drop|delete|take out)\s+(.+)/);
    if (removeMatch) {
      const target = removeMatch[1].replace(/[.!?]+$/, "").trim();
      if (/^day\s*\d+$/.test(target)) {
        say("Removing a whole day isn't supported yet — I can remove individual places though. Which one?");
        return "edit";
      }
      const all: Array<{ item: ItineraryItemRow; day: ItineraryDayRow }> = (t.itinerary?.days ?? []).flatMap((d) => d.items.map((item) => ({ item, day: d })));
      const matches = all.filter(({ item }) => item.title.toLowerCase().includes(target));
      if (matches.length === 0) {
        say(`I couldn't find "${target}" in your itinerary. Here's what's planned:\n${itinerarySummary(t)}`);
        return "edit";
      }
      if (matches.length > 1) {
        say(
          `A few things match "${target}" — which one?\n${matches.map(({ item, day }, i) => `${i + 1}. ${item.title} (Day ${day.day_number})`).join("\n")}`,
          matches.map(({ item, day }) => `${item.title} — Day ${day.day_number}`),
        );
        return "edit";
      }
      const { item, day } = matches[0];
      setBusy(true);
      try {
        await tripsApi.removeItem(t.id, item.id);
        const fresh = await tripsApi.detail(t.id);
        setEditTrip(fresh);
        say(
          `Removed ${item.title} from Day ${day.day_number}. ${fresh.itinerary?.days.some((d) => d.items.length > 0) ? "Anything else to adjust?" : "The itinerary is now empty — want me to add places back?"}`,
          ["Show my itinerary", "Open my trip"],
        );
        return "edit";
      } catch (err) {
        say(err instanceof Error ? `Couldn't remove it: ${err.message}` : "Couldn't remove that item.");
        return "edit";
      } finally {
        setBusy(false);
      }
    }

    // "add café to day 2" style custom items
    const addItem = q.match(/add\s+(.+?)\s+(?:to|on)\s+day\s*(\d{1,2})/);
    if (addItem) {
      const title = text.slice(text.toLowerCase().indexOf("add ") + 4).split(/\s+(?:to|on)\s+day/i)[0].trim();
      const dayNum = parseInt(addItem[2], 10);
      const dayExists = (t.itinerary?.days ?? []).some((d) => d.day_number === dayNum);
      if (!dayExists) {
        say(`Day ${dayNum} doesn't exist — your trip runs ${fmtDate(t.starts_on)} → ${fmtDate(t.ends_on)}.`);
        return "edit";
      }
      setBusy(true);
      try {
        await tripsApi.addCustomItem(t.id, dayNum, title);
        const fresh = await tripsApi.detail(t.id);
        setEditTrip(fresh);
        say(`Added "${title}" to Day ${dayNum}. Anything else?`, ["Show my itinerary", "Open my trip"]);
        return "edit";
      } catch (err) {
        say(err instanceof Error ? `Couldn't add it: ${err.message}` : "Couldn't add that.");
        return "edit";
      } finally {
        setBusy(false);
      }
    }

    say("I can remove a place (\"remove Raghurajpur\"), add a day (\"add one more day\"), or add something to a day (\"add seafood dinner to day 2\"). What would you like?", ["Show my itinerary"]);
    return "edit";
  }

  async function handleDone(text: string): Promise<Step> {
    if (/open|my trip|dashboard/i.test(text)) {
      // The chip promise: take the user to the trip they just built.
      router.push("/trips");
      setOpen(false);
      return "done";
    }
    if (/another|new|again/i.test(text)) {
      setDraft(EMPTY);
      setCreated(null);
      clearDraft();
      say("Let's plan another one. Is this your first time visiting India?", ["Yes, first time", "No, I've been before"]);
      return "firsttime";
    }
    say("You can open your trip from My Trips any time. Want to plan another journey?", ["Plan another"]);
    return "done";
  }

  const HANDLERS: Record<Step, (text: string) => Promise<Step>> = {
    firsttime: handleFirstTime, dmood: handleDiscoverMood, states: handleStates,
    city: handleCity, dates: handleDates, party: handleParty,
    budget: handleBudget, moods: handleMoods, confirm: handleConfirm, done: handleDone, edit: handleEdit,
  };

  async function send(raw?: string) {
    const text = (raw ?? input).trim();
    if (!text || busy) return;
    setInput("");
    reply(text);
    setBusy(true);
    try {
      // Escape hatch: restart/stop commands work from ANY step, so a user
      // is never trapped answering a question they've changed their mind about.
      if (/\bclassic (mode|vira|assistant)\b|switch (back )?to classic/i.test(text)) {
        setAiMode(false);
        setAiHistory([]);
        say("Classic Vira is back on. Is this your first time visiting India?", ["Yes, first time", "No, I've been before"]);
        setStep("firsttime");
        return;
      }
      if (/^(restart|start over|reset|cancel|stop|exit)/i.test(text.trim()) ||
          /\b(i want to (restart|start over|reset)|restart (the )?(chat|conversation|bot)|start from (the )?beginning|scratch)\b/i.test(text)) {
        setDraft(EMPTY);
        setCreated(null);
        setEditTrip(null);
        setDatePick({ start: "", end: "" });
        setAiHistory([]);
        clearDraft();
        if (aiMode) {
          setMsgs((m) => [...m, { from: "bot", ai: true, text: "Fresh start in AI mode — tell me where and when you'd like to go." }]);
        } else {
          say("No problem — starting fresh. Is this your first time visiting India?", ["Yes, first time", "No, I've been before"]);
        }
        // setStep must happen HERE: send()'s return value is discarded by the
        // chip/form callers, so returning "firsttime" alone left `step` stale
        // and the next answer was handled by the old step's handler.
        setStep("firsttime");
        return;
      }
      // Vira AI (beta) mode: free-form conversation with trip actions. The
      // restart escape hatch above still applies first. Any AI failure falls
      // back to the classic assistant with an honest note — never fake output.
      if (aiMode) {
        // Navigation chips work locally even in AI mode (they're UI actions,
        // not conversation — the LLM never needs to see them).
        if (/^open my trip$/i.test(text) && created) {
          router.push("/trips");
          setOpen(false);
          return;
        }
        if (/^show my itinerary$/i.test(text) && created) {
          try {
            const d = await tripsApi.detail(created.tripId);
            const lines = (d.itinerary?.days ?? [])
              .map((day) => `Day ${day.day_number}: ${day.items.map((i) => i.title).join(", ") || "free day"}`)
              .join("\n");
            setMsgs((m) => [...m, { from: "bot", ai: true, text: `Your ${d.city?.name ?? ""} plan (${d.starts_on} → ${d.ends_on}):\n${lines}`, chips: ["Open my trip"] }]);
          } catch {
            setMsgs((m) => [...m, { from: "bot", ai: true, text: "I couldn't load the itinerary just now — try again in a moment." }]);
          }
          return;
        }
        try {
          const res = await aiApi.chat(text, aiHistory);
          setMsgs((m) => [...m, { from: "bot", text: res.reply, ai: true }]);
          setAiHistory((h) => [...h, { role: "user", text }, { role: "bot", text: res.reply }].slice(-8));
          if (res.trip_id) {
            setCreated({ tripId: res.trip_id });
            setStep("done");
            setMsgs((m) => [
              ...m,
              { from: "bot", text: "Open it from the button below, or keep chatting — I can add places, extend days, or check the weather.", ai: true, chips: ["Open my trip", "Show my itinerary"] },
            ]);
          }
        } catch (e) {
          const msg = e instanceof Error ? e.message : "The AI is unavailable right now.";
          setMsgs((m) => [
            ...m,
            { from: "bot", text: `⚠️ Vira AI (beta): ${msg} Switching back to the classic assistant.`, ai: true },
          ]);
          setAiMode(false);
          setStep("firsttime");
        }
        return;
      }
      const next = await HANDLERS[step](text);
      setStep(next);
    } finally {
      setBusy(false);
    }
  }

  function toggleAiMode() {
    if (!user) {
      say("Vira AI (beta) personalizes answers using your trips, so it needs an account. Sign in and I'll turn it on!");
      return;
    }
    const next = !aiMode;
    setAiMode(next);
    setAiHistory([]);
    if (next) {
      setMsgs((m) => [
        ...m,
        { from: "bot", ai: true, text: "β Vira AI (beta) is on — I can chat freely, answer from verified Odisha data and your trip history, and create or edit trips for you. Say things like “plan 3 quiet days in Puri next month” or “what's the weather in Konark?”. Say “classic mode” any time to switch back." },
      ]);
    } else {
      setMsgs((m) => [...m, { from: "bot", text: "Classic Vira is back on. Is this your first time visiting India?" }]);
      setStep("firsttime");
    }
  }

  return (
    <>
      {/* Floating launcher */}
      <button
        type="button"
        onClick={() => (open ? setOpen(false) : begin())}
        aria-label={open ? "Close trip assistant" : "Open trip assistant"}
        className="fixed bottom-5 right-5 z-50 inline-flex h-14 w-14 items-center justify-center rounded-full bg-forest text-white shadow-xl transition-transform hover:scale-105"
      >
        {open ? <X className="h-6 w-6" aria-hidden="true" /> : <MessageCircle className="h-6 w-6" aria-hidden="true" />}
      </button>

      {/* "Ask Vira" entry popup — the site-entry greeting */}
      {teaser && !open && (
        <div
          role="status"
          className="fixed bottom-24 right-5 z-50 w-[min(88vw,300px)] rounded-2xl bg-white p-4 shadow-2xl ring-1 ring-ink/10"
        >
          <button
            type="button"
            onClick={dismissTeaser}
            aria-label="Dismiss assistant welcome"
            className="absolute right-2.5 top-2.5 rounded-full p-1 text-ink/40 transition-colors hover:text-ink"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
          <p className="flex items-center gap-2 text-sm font-semibold text-ink">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-forest text-white">
              <Bot className="h-4 w-4" aria-hidden="true" />
            </span>
            Ask Vira
          </p>
          <p className="mt-2 text-xs leading-relaxed text-ink/70">
            {"Namaste! I'm Vira, your trip assistant. Tell me your mood and dates — I'll build a day-by-day plan for you."}
          </p>
          <button
            type="button"
            onClick={begin}
            className="mt-3 w-full rounded-full bg-forest px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-forest-dark"
          >
            Start planning
          </button>
        </div>
      )}

      {open && (
        <div
          role="dialog"
          aria-label="Trip assistant chat"
          className="fixed bottom-24 right-5 z-50 flex h-[520px] w-[min(92vw,380px)] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl ring-1 ring-ink/10"
        >
          <header className="flex items-center gap-3 bg-forest px-4 py-3 text-white">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-white/15">
              <Bot className="h-5 w-5" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold">Vira {aiMode ? "AI" : "— trip assistant"}{aiMode ? "" : ""}</p>
              <p className="text-[11px] text-white/70">
                {aiMode ? "β AI mode · grounded in verified data" : "Rule-based guide · asks your basic needs"}
              </p>
            </div>
            <button
              type="button"
              onClick={toggleAiMode}
              className={`rounded-full px-3 py-1.5 text-[11px] font-semibold transition-colors ${
                aiMode ? "bg-amber-400 text-ink hover:bg-amber-300" : "bg-white/15 text-white hover:bg-white/25"
              }`}
              title={aiMode ? "Switch back to the classic assistant" : "Try the AI beta (signed-in users)"}
            >
              {aiMode ? "Exit β" : "Try Vira AI β"}
            </button>
            {voiceSupported && (
              <button
                type="button"
                onClick={toggleSpeak}
                aria-pressed={speakOn}
                aria-label={speakOn ? "Turn off spoken replies" : "Read replies aloud (beta)"}
                title={speakOn ? "Spoken replies are on (beta)" : "Read my replies aloud (beta)"}
                className={`inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors ${
                  speakOn ? "bg-amber-400 text-ink" : "bg-white/15 text-white hover:bg-white/25"
                }`}
              >
                {speakOn ? <Volume2 className="h-4 w-4" aria-hidden="true" /> : <VolumeX className="h-4 w-4" aria-hidden="true" />}
              </button>
            )}
          </header>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto bg-cream/60 px-4 py-4">
            {msgs.map((m, i) => (
              <div key={i} className={m.from === "user" ? "flex justify-end" : "flex justify-start"}>
                <div
                  className={`max-w-[85%] whitespace-pre-line rounded-2xl px-3.5 py-2.5 text-sm ${
                    m.from === "user"
                      ? "rounded-br-sm bg-forest text-white"
                      : m.ai
                        ? "rounded-bl-sm bg-white text-ink ring-2 ring-amber-400/60"
                        : "rounded-bl-sm bg-white text-ink ring-1 ring-ink/10"
                  }`}
                >
                  {m.ai && m.from === "bot" ? (
                    <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wide text-amber-600">
                      β Vira AI (beta)
                    </span>
                  ) : null}
                  {m.text}
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-2xl rounded-bl-sm bg-white px-3.5 py-2.5 text-sm text-ink/60 ring-1 ring-ink/10">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> thinking…
                </div>
              </div>
            )}
          </div>

          {/* Quick replies */}
          {msgs.length > 0 && msgs[msgs.length - 1].chips && !busy && (
            <div className="flex flex-wrap gap-1.5 border-t border-ink/10 bg-white px-3 pt-2.5">
              {msgs[msgs.length - 1].chips!.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => void send(c)}
                  className="rounded-full border border-forest/40 px-3 py-1.5 text-xs font-medium text-forest transition-colors hover:bg-forest hover:text-white"
                >
                  {c}
                </button>
              ))}
            </div>
          )}

          {/* Calendar picker for the dates step (typers still welcome) */}
          {step === "dates" && !busy && (
            <div className="border-t border-ink/10 bg-white px-3 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <label className="text-xs font-medium text-ink/60">
                  Pick dates
                  <input
                    type="date"
                    value={datePick.start}
                    onChange={(e) => setDatePick((p) => ({ ...p, start: e.target.value }))}
                    aria-label="Trip start date"
                    className="ml-1 rounded-full border border-ink/15 px-2.5 py-1.5 text-xs outline-none focus:border-forest"
                  />
                </label>
                <span className="text-xs text-ink/40">to</span>
                <input
                  type="date"
                  value={datePick.end}
                  min={datePick.start || undefined}
                  onChange={(e) => setDatePick((p) => ({ ...p, end: e.target.value }))}
                  aria-label="Trip end date"
                  className="rounded-full border border-ink/15 px-2.5 py-1.5 text-xs outline-none focus:border-forest"
                />
                <button
                  type="button"
                  disabled={!datePick.start}
                  onClick={() => {
                    const text = datePick.end
                      ? `${datePick.start} to ${datePick.end}`
                      : datePick.start;
                    void send(text);
                    setDatePick({ start: "", end: "" });
                  }}
                  className="rounded-full bg-forest px-3.5 py-1.5 text-xs font-semibold text-white disabled:opacity-40"
                >
                  Use these dates
                </button>
              </div>
              <p className="mt-1.5 text-[11px] text-ink/40">
                Leave the end blank for a suggested 3-day trip.
              </p>
            </div>
          )}

          {micHint && listening && (
            <div className="bg-white px-4 pt-1 text-center text-[11px] font-medium text-forest/80">
              {micHint}
            </div>
          )}

          <form
            onSubmit={(e) => { e.preventDefault(); void send(); }}
            className="flex items-center gap-2 bg-white p-3"
          >
            {voiceSupported && (
              <div className="relative shrink-0">
                <select
                  value={voiceLang}
                  onChange={(e) => setVoiceLangManual(e.target.value)}
                  aria-label="Voice language"
                  title="Voice language — Auto follows whatever you speak"
                  className="max-w-[86px] cursor-pointer appearance-none rounded-full border border-ink/15 bg-white py-2 pl-3 pr-6 text-[11px] font-semibold text-ink/70 outline-none focus:border-forest"
                >
                  <option value="auto">Auto ▾</option>
                  {VOICE_LANGS.map((l) => (
                    <option key={l.code} value={l.code}>{l.label}</option>
                  ))}
                </select>
              </div>
            )}
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                listening
                  ? "Listening… speak now"
                  : step === "done"
                    ? "Plan another trip?"
                    : "Type your answer…"
              }
              aria-label="Message the trip assistant"
              className="w-full rounded-full border border-ink/15 px-4 py-2.5 text-sm outline-none focus:border-forest"
            />
            {voiceSupported && (
              <button
                type="button"
                onClick={() => (listening ? stopListening() : startListening())}
                disabled={busy && !listening}
                aria-pressed={listening}
                aria-label={listening ? "Stop voice input" : "Answer by voice (beta)"}
                title={listening ? "Stop listening" : "Answer by voice (beta)"}
                className={`inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border transition-colors ${
                  listening
                    ? "animate-pulse border-red-300 bg-red-500 text-white"
                    : "border-ink/15 bg-white text-ink/60 hover:border-forest hover:text-forest disabled:opacity-40"
                }`}
              >
                <Mic className="h-4 w-4" aria-hidden="true" />
              </button>
            )}
            <button
              type="submit"
              disabled={!input.trim() || busy}
              aria-label="Send"
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-forest text-white disabled:opacity-40"
            >
              <Send className="h-4 w-4" aria-hidden="true" />
            </button>
          </form>
        </div>
      )}
    </>
  );
}
