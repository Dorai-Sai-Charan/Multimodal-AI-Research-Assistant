"use client";

import { RotateCcw, Sparkles, Target, Wand2 } from "lucide-react";
import { useState } from "react";
import { Button } from "./ui/button";
import { Slider } from "./ui/slider";
import { Select } from "./ui/select";
import { Input } from "./ui/input";
import { Collapsible } from "./ui/collapsible";
import { useAppStore } from "@/lib/store";

export function ModelSettings() {
  const settings = useAppStore((s) => s.settings);
  const catalogue = useAppStore((s) => s.catalogue);
  const setSetting = useAppStore((s) => s.setSetting);
  const resetSettings = useAppStore((s) => s.resetSettings);
  const applyPreset = useAppStore((s) => s.applyPreset);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const modelInfo = catalogue.models.find((m) => m.id === settings.model);

  return (
    <Collapsible
      title="Model Settings"
      icon={<Sparkles className="w-3.5 h-3.5" />}
    >
      <div className="space-y-4 pt-2">
        {/* Presets */}
        <div>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-2 font-medium">
            Quick presets
          </p>
          <div className="grid grid-cols-3 gap-1.5">
            <button
              onClick={() => applyPreset("precise")}
              className="flex flex-col items-center gap-1 p-2 rounded-lg bg-bg-subtle border border-border hover:border-brand-500/50 hover:bg-bg-elevated transition-all text-xs text-slate-300 hover:text-white"
              title="Low randomness — best for RAG, extraction, citations"
            >
              <Target className="w-3.5 h-3.5" />
              Precise
            </button>
            <button
              onClick={() => applyPreset("balanced")}
              className="flex flex-col items-center gap-1 p-2 rounded-lg bg-bg-subtle border border-border hover:border-brand-500/50 hover:bg-bg-elevated transition-all text-xs text-slate-300 hover:text-white"
              title="Default Q&A — middle-ground creativity"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Balanced
            </button>
            <button
              onClick={() => applyPreset("creative")}
              className="flex flex-col items-center gap-1 p-2 rounded-lg bg-bg-subtle border border-border hover:border-brand-500/50 hover:bg-bg-elevated transition-all text-xs text-slate-300 hover:text-white"
              title="Higher randomness — brainstorming, summaries"
            >
              <Wand2 className="w-3.5 h-3.5" />
              Creative
            </button>
          </div>
        </div>

        <div className="h-px bg-border" />

        {/* Model */}
        <div>
          <label className="text-sm text-slate-300 font-medium mb-1.5 block">
            Model
          </label>
          <Select
            value={settings.model}
            onChange={(v) => setSetting("model", v)}
            options={catalogue.models.map((m) => ({
              value: m.id,
              label: m.label,
            }))}
          />
          {modelInfo?.best_for && (
            <p className="mt-1.5 text-[11px] text-slate-500 leading-snug">
              <span className="text-brand-400 font-medium">Best for:</span>{" "}
              {modelInfo.best_for}
            </p>
          )}
        </div>

        <Slider
          label="Temperature"
          value={settings.temperature}
          min={0}
          max={1.5}
          step={0.05}
          onChange={(v) => setSetting("temperature", v)}
          help="Higher = more creative; lower = more deterministic and factual."
          format={(v) => v.toFixed(2)}
        />
        <Slider
          label="Max tokens"
          value={settings.max_tokens}
          min={256}
          max={8192}
          step={128}
          onChange={(v) => setSetting("max_tokens", v)}
          help="Hard cap on the length of the model's response."
        />
        <Slider
          label="Retrieval top-k"
          value={settings.top_k}
          min={1}
          max={30}
          step={1}
          onChange={(v) => setSetting("top_k", v)}
          help="How many document chunks to retrieve as context."
        />

        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-xs text-brand-400 hover:text-brand-300 font-medium"
        >
          {showAdvanced ? "– Hide" : "+ Show"} advanced parameters
        </button>

        {showAdvanced && (
          <div className="space-y-4 pt-2 border-t border-border/50">
            <Slider
              label="Top-p (nucleus)"
              value={settings.top_p}
              min={0}
              max={1}
              step={0.05}
              onChange={(v) => setSetting("top_p", v)}
              format={(v) => v.toFixed(2)}
              help="Smallest set of tokens whose probabilities sum to p; 1.0 disables."
            />
            <Slider
              label="Frequency penalty"
              value={settings.frequency_penalty}
              min={-2}
              max={2}
              step={0.1}
              onChange={(v) => setSetting("frequency_penalty", v)}
              format={(v) => v.toFixed(1)}
              help="Positive values reduce verbatim repetition."
            />
            <Slider
              label="Presence penalty"
              value={settings.presence_penalty}
              min={-2}
              max={2}
              step={0.1}
              onChange={(v) => setSetting("presence_penalty", v)}
              format={(v) => v.toFixed(1)}
              help="Positive values push toward new topics."
            />
            <Slider
              label="Similarity threshold"
              value={settings.similarity_threshold}
              min={0}
              max={1}
              step={0.05}
              onChange={(v) => setSetting("similarity_threshold", v)}
              format={(v) => v.toFixed(2)}
              help="Minimum relevance score a retrieved chunk must have."
            />
            <div>
              <label className="text-sm text-slate-300 font-medium mb-1.5 block">
                Seed (blank = random)
              </label>
              <Input
                type="number"
                value={settings.seed ?? ""}
                onChange={(e) => {
                  const v = e.target.value;
                  setSetting("seed", v === "" ? null : Number(v));
                }}
                placeholder="random"
              />
              <p className="mt-1 text-[11px] text-slate-500">
                Fixed seed makes outputs reproducible.
              </p>
            </div>
            {modelInfo?.supports_reasoning_effort ? (
              <div>
                <label className="text-sm text-slate-300 font-medium mb-1.5 block">
                  Reasoning effort
                </label>
                <Select
                  value={settings.reasoning_effort}
                  onChange={(v) =>
                    setSetting("reasoning_effort", v as "low" | "medium" | "high")
                  }
                  options={[
                    { value: "low", label: "Low — fastest" },
                    { value: "medium", label: "Medium — balanced" },
                    { value: "high", label: "High — most thorough" },
                  ]}
                />
              </div>
            ) : (
              <p className="text-[11px] text-slate-500 italic">
                Reasoning effort not supported by the selected model.
              </p>
            )}
          </div>
        )}

        <Button
          variant="ghost"
          fullWidth
          onClick={resetSettings}
          className="text-xs"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          Reset to defaults
        </Button>
      </div>
    </Collapsible>
  );
}
