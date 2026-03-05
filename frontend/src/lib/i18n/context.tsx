"use client";

import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import zh, { type TranslationKey } from "./zh";
import en from "./en";

export type Locale = "zh" | "en";

const dictionaries: Record<Locale, Record<TranslationKey, string>> = { zh, en };

interface LocaleContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: TranslationKey) => string;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

function detectDefaultLocale(): Locale {
  if (typeof window === "undefined") return "en";
  try {
    const saved = localStorage.getItem("mutelens-locale");
    if (saved === "en" || saved === "zh") return saved;
  } catch {}
  return "en";
}

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setLocaleState(detectDefaultLocale());
    setMounted(true);
  }, []);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    try {
      localStorage.setItem("mutelens-locale", l);
    } catch {}
  }, []);

  const t = useCallback(
    (key: TranslationKey) => dictionaries[locale][key] ?? key,
    [locale],
  );

  if (!mounted) {
    const fallbackT = (key: TranslationKey) => en[key] ?? key;
    return (
      <LocaleContext.Provider value={{ locale: "en", setLocale, t: fallbackT }}>
        {children}
      </LocaleContext.Provider>
    );
  }

  return (
    <LocaleContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </LocaleContext.Provider>
  );
}

export function useLocale(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used within LocaleProvider");
  return ctx;
}
