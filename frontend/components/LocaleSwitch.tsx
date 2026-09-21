"use client";

import { useTranslations } from "next-intl";
import { LOCALES, type Locale } from "@/i18n/locales";
import { LanguageIcon } from "./SwitchIcons";

/** Two-way language toggle (한국어 / English). Each option is labelled in its own language. */
export function LocaleSwitch({
  value,
  onChange,
  disabled,
  className = "",
}: {
  value: Locale;
  onChange: (locale: Locale) => void;
  disabled?: boolean;
  className?: string;
}) {
  const t = useTranslations("common");
  return (
    <div
      className={`locale-switch ${className}`}
      role="radiogroup"
      aria-label={t("languageHint")}
      title={t("languageHint")}
    >
      <span className="locale-switch__icon">
        <LanguageIcon />
      </span>
      {LOCALES.map((l) => (
        <button
          key={l}
          type="button"
          role="radio"
          lang={l}
          aria-checked={value === l}
          className={value === l ? "is-on" : ""}
          disabled={disabled}
          onClick={() => value !== l && onChange(l)}
        >
          {t(`localeName.${l}`)}
        </button>
      ))}
    </div>
  );
}
