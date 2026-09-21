"use client";

import { useMemo, useState } from "react";
import { OperatorApiError, operatorApi } from "@/lib/operator/api";
import {
  addLanguage,
  asShapeOf,
  getIn,
  parseBundle,
  placeholders,
  serializeBundle,
  setIn,
  textOf,
  type BundleDoc,
  type Json,
} from "@/lib/operator/draft";
import { changedRefs, type Ref } from "@/lib/operator/refs";
import type { Bump, ConfigStatus, ValidateResult, VersionDetail } from "@/lib/operator/types";
import { nextVersion } from "@/lib/operator/versions";
import type { HighlightRefs } from "./types";

type Props = {
  base: VersionDetail;
  published: string[];
  status: ConfigStatus | null;
  onChanges: HighlightRefs;
  onRefs: HighlightRefs;
  onClear: () => void;
  onPublished: (version: string) => void;
};

type Path = (string | number)[];

const MODEL_ARGS: { key: string; label: string; step?: string }[] = [
  { key: "temperature", label: "temperature", step: "0.1" },
  { key: "top_p", label: "top_p", step: "0.05" },
  { key: "max_tokens", label: "max tokens", step: "1" },
];

function obj(value: unknown): Json {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Json) : {};
}

function changeCaption(refs: Ref[]): string {
  return refs.length ? `This draft changes ${refs.length} config entr${refs.length === 1 ? "y" : "ies"}` : "";
}

/**
 * A new version, edited field by field from `base`: models, prompts, copy per language, labels, billing units,
 * languages. The backend validates it and publishes it as the next version.
 */
export function EditTab({ base, published, status, onChanges, onRefs, onClear, onPublished }: Props) {
  const baseDoc = useMemo(() => parseBundle(base.files), [base.files]);
  const [doc, setDoc] = useState<BundleDoc>(baseDoc);
  const [filter, setFilter] = useState("");
  const [changedOnly, setChangedOnly] = useState(false);
  const [newLang, setNewLang] = useState({ code: "", name: "" });
  const [result, setResult] = useState<ValidateResult | null>(null);
  const [error, setError] = useState<{ message: string; problems: string[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState("");
  const [bump, setBump] = useState<Bump>("patch");

  const files = useMemo(() => serializeBundle(doc), [doc]);
  const changed = useMemo(() => changedRefs(base.files, files), [base.files, files]);
  const changedSet = useMemo(() => new Set(changed), [changed]);
  const languages = Object.keys(obj(doc.config.languages));
  const addsLanguage = languages.length > Object.keys(obj(baseDoc.config.languages)).length;
  const effectiveBump: Bump = addsLanguage ? "minor" : bump;
  const target = nextVersion(published, String(doc.config.version ?? base.version), effectiveBump);
  const readOnly = status !== null && !status.publishable;

  // Tell the agent loop what changed from the change itself, not from an effect.
  const commit = (next: BundleDoc) => {
    setDoc(next);
    setResult(null);
    const refs = changedRefs(base.files, serializeBundle(next));
    onChanges(refs, changeCaption(refs));
  };
  const update = (path: Path, value: unknown) => commit(setIn(doc, path, value));

  const q = filter.trim().toLowerCase();
  const visible = (ref: Ref, ...texts: string[]) =>
    (!changedOnly || changedSet.has(ref)) && (!q || [ref, ...texts].some((t) => t.toLowerCase().includes(q)));

  const hover = (ref: Ref, label: string) => ({
    onMouseEnter: () => onRefs([ref], label),
    onMouseLeave: onClear,
    onFocus: () => onRefs([ref], label),
    onBlur: onClear,
  });

  // A plain function, not a component: a component defined here would remount (and drop focus) on every keystroke.
  function field(key: string, path: Path, ref: Ref, label: string, rows = 2) {
    const value = getIn(doc, path);
    const text = textOf(value);
    const baseText = textOf(getIn(baseDoc, path));
    const used = placeholders(baseText);
    const dropped = used.filter((p) => !placeholders(text).includes(p));
    return (
      <label key={key} className={`op-field${text !== baseText ? " op-field--dirty" : ""}`} {...hover(ref, label)}>
        <span className="op-field__label">{label}</span>
        <textarea
          className="op-field__input"
          rows={rows}
          value={text}
          onChange={(e) => update(path, asShapeOf(value, e.target.value))}
          spellCheck={false}
        />
        {used.length > 0 && (
          <span className="op-field__hint">
            uses {used.map((p) => `{${p}}`).join(" ")}
            {dropped.length > 0 && <b> · no longer uses {dropped.map((p) => `{${p}}`).join(" ")}</b>}
          </span>
        )}
      </label>
    );
  }

  async function run<T>(fn: () => Promise<T>): Promise<T | null> {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(
        e instanceof OperatorApiError ? { message: e.message, problems: e.problems } : { message: String(e), problems: [] },
      );
      return null;
    } finally {
      setBusy(false);
    }
  }

  const models = obj(doc.config.models);
  const profiles = Object.keys(models);
  const flowNames = Object.keys(doc.flows);
  const sections: [string, string][] = [
    ["models", "Models"],
    ["system", "System prompt"],
    ...flowNames.map((f): [string, string] => [`flow-${f}`, f]),
    ["labels", "Field labels"],
    ["billing", "Billing units"],
    ["languages", "Languages"],
  ];

  return (
    <div className="op-editor-layout">
      <nav className="op-editor-nav" aria-label="Sections">
        {sections.map(([id, label]) => (
          <a key={id} href={`#op-sec-${id}`}>
            {label}
          </a>
        ))}
      </nav>

      <div className="op-editor-main">
        {readOnly && (
          <div className="op-banner">
            This backend runs the bundled baseline (no AGENT_CONFIG_URI): drafts can be validated, not published.
          </div>
        )}
        <div className="op-editor-tools">
          <input
            type="search"
            placeholder="Find a field: key, node or text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <label>
            <input type="checkbox" checked={changedOnly} onChange={(e) => setChangedOnly(e.target.checked)} /> changed
            only ({changed.length})
          </label>
        </div>

        <section className="op-card" id="op-sec-models">
          <div className="op-card__title">Model profiles</div>
          <table className="op-table">
            <thead>
              <tr>
                <th>Profile</th>
                <th>Model id</th>
                {MODEL_ARGS.map((a) => (
                  <th key={a.key}>{a.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {profiles
                .filter((name) => visible(`models:${name}`, String(obj(models[name]).model_id)))
                .map((name) => {
                  const ref = `models:${name}`;
                  const args = obj(obj(models[name]).args);
                  return (
                    <tr key={name} className={changedSet.has(ref) ? "op-row--dirty" : ""} {...hover(ref, `Model profile “${name}”`)}>
                      <td className="op-mono">{name}</td>
                      <td>
                        <input
                          className="op-input op-mono"
                          value={String(obj(models[name]).model_id ?? "")}
                          onChange={(e) => update(["config", "models", name, "model_id"], e.target.value)}
                        />
                      </td>
                      {MODEL_ARGS.map((a) => (
                        <td key={a.key}>
                          <input
                            className="op-input op-input--num"
                            type="number"
                            step={a.step}
                            value={args[a.key] === undefined ? "" : String(args[a.key])}
                            placeholder="default"
                            onChange={(e) => {
                              const next = { ...args };
                              if (e.target.value === "") delete next[a.key];
                              else next[a.key] = Number(e.target.value);
                              update(["config", "models", name, "args"], next);
                            }}
                          />
                        </td>
                      ))}
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </section>

        {visible("system_prompt", textOf(doc.config.system_prompt)) && (
          <section className="op-card" id="op-sec-system">
            <div className="op-card__title">System prompt · every LLM node</div>
            <div className="op-card__body">
              {field("system_prompt", ["config", "system_prompt"], "system_prompt", "system prompt", 6)}
            </div>
          </section>
        )}

        {flowNames.map((flow) => {
          const data = doc.flows[flow].data;
          const llm = obj(data.llm);
          const copy = obj(data.copy);
          const nodes = Object.keys(llm).filter((node) =>
            Object.keys(obj(llm[node])).some((part) =>
              visible(`llm:${node}.${part}`, node, textOf(obj(llm[node])[part])),
            ),
          );
          const keys = Object.keys(copy).filter((key) =>
            visible(`copy:${flow}.${key}`, ...languages.map((l) => textOf(obj(copy[key])[l]))),
          );
          if (!nodes.length && !keys.length) return <div key={flow} id={`op-sec-flow-${flow}`} />;
          return (
            <section className="op-card" key={flow} id={`op-sec-flow-${flow}`}>
              <div className="op-card__title">
                <span className="op-mono">{flow}</span>
                <span className="op-empty">flows/{flow}.json</span>
              </div>
              <div className="op-card__body op-fields">
                {nodes.map((node) => {
                  const parts = obj(llm[node]);
                  const modelRef = `llm:${node}.model`;
                  return (
                    <div className="op-node" key={node}>
                      <div className="op-node__head" {...hover(modelRef, `${node}'s model profile`)}>
                        <span className="op-mono">{node}</span> runs on
                        <select
                          value={String(parts.model ?? "default")}
                          onChange={(e) => update([flow, "llm", node, "model"], e.target.value)}
                          className={changedSet.has(modelRef) ? "op-select--dirty" : ""}
                        >
                          {profiles.map((p) => (
                            <option key={p} value={p}>
                              {p}
                            </option>
                          ))}
                        </select>
                      </div>
                      {Object.keys(parts)
                        .filter((part) => part !== "model")
                        .map((part) =>
                          field(
                            part,
                            [flow, "llm", node, part],
                            `llm:${node}.${part}`,
                            `${node} · ${part}`,
                            part === "instructions" ? 5 : 2,
                          ),
                        )}
                    </div>
                  );
                })}
                {keys.map((key) => (
                  <div className="op-copy" key={key}>
                    <div className="op-copy__key op-mono">{key}</div>
                    <div className="op-copy__langs">
                      {languages.map((lang) => field(lang, [flow, "copy", key, lang], `copy:${flow}.${key}`, lang))}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          );
        })}

        {(
          [
            ["labels", "Field labels · asked for by name", "labels"],
            ["billing", "Billing units · shown with prices", "billing_periods"],
          ] as const
        ).map(([id, title, key]) => {
          const entries = Object.keys(obj(doc.config[key])).filter((field) =>
            visible(`${key}:${field}`, ...languages.map((l) => textOf(obj(obj(doc.config[key])[field])[l]))),
          );
          return (
            <section className="op-card" id={`op-sec-${id}`} key={id}>
              <div className="op-card__title">{title}</div>
              <table className="op-table">
                <thead>
                  <tr>
                    <th>Field</th>
                    {languages.map((l) => (
                      <th key={l}>{l}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {entries.map((field) => {
                    const ref = `${key}:${field}`;
                    return (
                      <tr key={field} className={changedSet.has(ref) ? "op-row--dirty" : ""} {...hover(ref, `${key.replace("_", " ")} · ${field}`)}>
                        <td className="op-mono">{field}</td>
                        {languages.map((l) => (
                          <td key={l}>
                            <input
                              className="op-input"
                              value={textOf(obj(obj(doc.config[key])[field])[l])}
                              onChange={(e) => update(["config", key, field, l], e.target.value)}
                            />
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </section>
          );
        })}

        <section className="op-card" id="op-sec-languages">
          <div className="op-card__title">Languages</div>
          <div className="op-card__body op-fields">
            {languages.map((code) => (
              <div className="op-lang" key={code} {...hover("languages", `Language ${code}`)}>
                <span className="op-mono">{code}</span>
                <input
                  className="op-input"
                  value={textOf(obj(obj(doc.config.languages)[code]).name)}
                  onChange={(e) => update(["config", "languages", code, "name"], e.target.value)}
                  aria-label={`${code} name, as the LLM is told to reply in`}
                />
                <label>
                  <input
                    type="radio"
                    checked={doc.config.default_language === code}
                    onChange={() => update(["config", "default_language"], code)}
                  />{" "}
                  default
                </label>
              </div>
            ))}
            <div className="op-lang">
              <input
                className="op-input op-mono"
                placeholder="code, e.g. ja"
                value={newLang.code}
                onChange={(e) => setNewLang({ ...newLang, code: e.target.value.trim() })}
              />
              <input
                className="op-input"
                placeholder="name, e.g. Japanese"
                value={newLang.name}
                onChange={(e) => setNewLang({ ...newLang, name: e.target.value })}
              />
              <button
                type="button"
                className="op-btn"
                disabled={!/^[a-z]{2,3}(-[A-Z]{2})?$/.test(newLang.code) || !newLang.name.trim() || languages.includes(newLang.code)}
                onClick={() => {
                  commit(addLanguage(doc, newLang.code, newLang.name.trim()));
                  setNewLang({ code: "", name: "" });
                }}
              >
                Add language
              </button>
            </div>
            <div className="op-empty">
              A new language starts with every text in the default language, to translate here. It is a minor version.
            </div>
          </div>
        </section>
        <aside className="op-publishbar" aria-label="Check and publish">
          {result?.ok && <div className="op-ok">Valid: the agent can load this version.</div>}
          {result && !result.ok && (
            <ul className="op-problems">
              {result.problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
          {error && (
            <ul className="op-problems">
              <li>{error.message}</li>
              {error.problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
          <div className="op-publishbar__row">
            <span
              className="op-radio"
              title="patch: wording, prompts, models · minor: adds a language, key or label"
            >
              <label>
                <input
                  type="radio"
                  disabled={addsLanguage}
                  checked={effectiveBump === "patch"}
                  onChange={() => setBump("patch")}
                />{" "}
                patch
              </label>
              <label>
                <input type="radio" checked={effectiveBump === "minor"} onChange={() => setBump("minor")} /> minor
              </label>
            </span>
            <span className="op-mono" title={`from ${base.version}; the backend keeps its version until it restarts`}>
              → {target}
            </span>
            <input
              className="op-input"
              placeholder="What changed, and why"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
            <button
              type="button"
              className="op-btn"
              disabled={busy}
              onClick={() => run(() => operatorApi.validate(files)).then((r) => r && setResult(r))}
            >
              Validate
            </button>
            <button
              type="button"
              className="op-btn op-btn--primary"
              disabled={busy || !changed.length || readOnly || !notes.trim()}
              title={!notes.trim() ? "Say what changed" : undefined}
              onClick={() =>
                run(() => operatorApi.publish(files, notes, effectiveBump)).then((r) => r && onPublished(r.version))
              }
            >
              Publish {target}
            </button>
            <button type="button" className="op-btn" disabled={busy || !changed.length} onClick={() => commit(baseDoc)}>
              Discard
            </button>
          </div>
        </aside>
      </div>

    </div>
  );
}
