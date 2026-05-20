"""
Humanizer Engine — Advanced text humanization with iterative refinement.
- AI Detection: roberta-base-openai-detector + heuristic metrics (blended)
- Humanization: Gemini with aggressive prompt + iterative refinement until <20%
- Computable metrics: burstiness, TTR, human markers
"""

import re
import json
import math
import logging
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from src.generation.llm_client import LLMClient

logger = logging.getLogger(__name__)

# Target AI score - we keep humanizing until we get below this
TARGET_AI_SCORE = 20
MAX_HUMANIZATION_PASSES = 3


# =============================================================================
# Computable Text Metrics (fast, local, no API)
# =============================================================================

def tokenize(text: str) -> list[str]:
    """Split text into words."""
    return [w for w in re.split(r"\s+", text.strip()) if w]


def split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    sentences = re.findall(r"[^.!?]+[.!?]+", text)
    if not sentences:
        return [text]
    return [s.strip() for s in sentences if s.strip()]


def compute_metrics(text: str) -> dict:
    """Compute objective text metrics."""
    if not text or not text.strip():
        return None

    words = tokenize(text)
    sentences = split_sentences(text)
    word_count = len(words)
    sentence_count = len(sentences)

    # Sentence length variance (burstiness proxy)
    sentence_lengths = [len(tokenize(s)) for s in sentences]
    avg_sent_len = sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0
    variance = sum((l - avg_sent_len) ** 2 for l in sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0
    std_dev = math.sqrt(variance)
    burstiness = std_dev / (avg_sent_len or 1)

    # Type-Token Ratio (lexical diversity)
    clean_words = [re.sub(r"[^a-z]", "", w.lower()) for w in words]
    clean_words = [w for w in clean_words if w]
    unique_words = set(clean_words)
    ttr = len(unique_words) / (len(clean_words) or 1)

    # Human markers
    has_em_dash = bool(re.search(r"—", text))
    has_parenthetical = bool(re.search(r"\([^)]+\)", text))
    starts_with_but_and = len([s for s in sentences if re.match(r"^(but|and|so|yet)\b", s, re.IGNORECASE)])
    has_contractions = bool(re.search(r"\b\w+'(s|t|re|ve|ll|d|m)\b", text, re.IGNORECASE))
    human_markers = sum([has_em_dash, has_parenthetical, starts_with_but_and > 0, has_contractions])

    # Transition word density — high density of academic transitions inflates AI probability
    _TRANSITIONS = [
        "furthermore", "moreover", "additionally", "in conclusion",
        "it is worth noting", "it should be noted", "consequently",
        "therefore", "thus", "hence", "in summary", "to summarize",
        "in addition", "as a result", "this suggests", "this indicates",
    ]
    text_lower_for_transitions = text.lower()
    transition_hits = sum(text_lower_for_transitions.count(t) for t in _TRANSITIONS)
    transition_density = transition_hits / (word_count / 100) if word_count > 0 else 0  # per 100 words

    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "avg_sentence_length": round(avg_sent_len, 1),  # Fix 15: renamed from avg_sent_len
        "std_dev": round(std_dev, 1),
        "burstiness": round(burstiness, 2),
        "ttr": round(ttr, 2),
        "human_markers": human_markers,
        "has_em_dash": has_em_dash,
        "has_parenthetical": has_parenthetical,
        "starts_with_but_and": starts_with_but_and,
        "has_contractions": has_contractions,
        "transition_density": round(transition_density, 2),
    }


def heuristic_ai_score(m: dict) -> float:
    """Compute heuristic AI score from metrics (0-100, higher = more AI)."""
    if not m:
        return 0

    score = 50  # neutral start

    # Burstiness — human text has burstiness > 0.5 typically
    if m["burstiness"] < 0.3:
        score += 25  # very uniform = AI
    elif m["burstiness"] < 0.5:
        score += 12
    elif m["burstiness"] > 0.8:
        score -= 25  # very high variance = very human
    elif m["burstiness"] > 0.6:
        score -= 18
    else:
        score -= 8

    # Sentence length uniformity: very low std_dev is a strong AI signal
    std_dev = m.get("std_dev", 0)
    if std_dev < 3:
        score += 15  # nearly identical sentence lengths → AI
    elif std_dev < 5:
        score += 7

    # Average sentence length — AI clusters around 20-25 words
    if 19 <= m["avg_sentence_length"] <= 26:
        score += 12
    elif m["avg_sentence_length"] < 12 or m["avg_sentence_length"] > 30:
        score -= 10

    # Type-token ratio (lexical diversity) — very low TTR = AI
    if m["ttr"] < 0.4:
        score += 18  # very low diversity
    elif m["ttr"] < 0.45:
        score += 10
    elif m["ttr"] > 0.7:
        score -= 15
    elif m["ttr"] > 0.6:
        score -= 8

    # Human markers - strong indicator
    score -= m["human_markers"] * 8

    # Transition word density — very high density indicates AI over-reliance on connectors
    transition_density = m.get("transition_density", 0)
    if transition_density > 3:
        score += 15  # extremely dense academic transitions
    elif transition_density > 1.5:
        score += 8

    return max(0, min(100, round(score)))


# =============================================================================
# Humanize Prompts (aggressive, with intensity levels)
# =============================================================================

HUMANIZE_PROMPT_TEMPLATE = """You are rewriting academic text so it scores BELOW 20% on AI detectors (GPTZero, Turnitin, Copyleaks). These tools measure perplexity and burstiness — not prose quality. Your goal: text that passes as human-written for IEEE academic papers.

{retry_context}

CRITICAL RULES — follow ALL strictly:

1. **BURSTINESS (most important)**: Mix sentence lengths AGGRESSIVELY.
   - Some sentences: 4-8 words (short, punchy)
   - Others: 25-35 words (long, with embedded clauses, em-dashes, parentheticals)
   - NEVER write 3 similar-length sentences in a row
   - Target coefficient of variation > 0.7

2. **PERPLEXITY**: Pick unexpected-but-accurate words.
   - "show" or "reveal" instead of "demonstrate"
   - "use" instead of "utilize"
   - "real" or "marked" instead of "significant"
   - "approach" instead of "methodology"
   - "help" instead of "facilitate"
   Replace ALL predictable academic clichés.

3. **HUMAN MARKERS — include AT LEAST 4**:
   - At least one sentence starting with "But" or "And"
   - At least one em-dash aside — like this — mid-sentence
   - At least one parenthetical remark (even brief)
   - At least one short fragment for emphasis (3-5 words)
   - Vary sentence openers (don't start every sentence with "The")

4. **STRUCTURAL DISRUPTION**: Don't follow claim → evidence → transition.
   - Sometimes lead with the implication
   - Sometimes pose a question
   - Drop formal transitions (Therefore, Hence, Furthermore, Moreover)
   - Mix declarative with rhetorical

5. **GRAMMAR**: Perfect grammar, proper punctuation, IEEE-paper appropriate.

6. **PRESERVE**: All facts, citations [#], numbers, technical terms, references.

7. **TONE**: Scholarly but natural. Suitable for IEEE papers - professional yet human.

CRITICAL REQUIREMENTS FOR HUMANIZATION:
- Vary sentence lengths dramatically: mix very short sentences (4-6 words) with longer ones (20-30 words)
- Use contractions naturally: "don't", "it's", "we've", "they're"
- Add occasional first-person perspective where appropriate
- Break up strings of similarly-structured sentences
- Include a personal or conversational aside occasionally
- Avoid starting multiple consecutive sentences with the same word
- Use informal connectors occasionally: "But", "So", "Yet", "Still"
- Mix active and passive voice unpredictably

TEXT TO REWRITE:
{text}

Respond ONLY with valid JSON (no markdown fences, no preamble):
{{"humanized": "<rewritten text>", "changes": ["<change 1>", "<change 2>", "<change 3>"]}}"""


RETRY_TEMPLATE = """**RETRY ATTEMPT {attempt}**: Your previous version scored {prev_score}% AI. We need to push harder!

The previous output was:
"{prev_text}"

This time:
- Vary sentence lengths even more DRAMATICALLY (mix 4-word sentences with 30+ word sentences)
- Add MORE em dashes, parentheticals
- Use MORE unexpected word choices
- Add MORE sentences starting with "But", "And", "Yet"
- Break up uniform rhythm completely
"""


# =============================================================================
# Main Engine
# =============================================================================

class HumanizationEngine:
    """Advanced humanizer with iterative refinement until target score reached."""

    def __init__(self):
        logger.info("Initializing HumanizationEngine...")

        # AI Detection: RoBERTa detector
        try:
            logger.info("Loading roberta-base-openai-detector...")
            self.detector_tokenizer = AutoTokenizer.from_pretrained("roberta-base")
            self.detector_model = AutoModelForSequenceClassification.from_pretrained(
                "openai-community/roberta-base-openai-detector"
            )
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.detector_model.to(self.device)
            logger.info(f"✓ AI detector loaded on {self.device}")
        except Exception as e:
            logger.error(f"Failed to load detector model: {e}")
            self.detector_model = None
            self.detector_tokenizer = None

        # Humanization: Groq LLM
        try:
            self.llm = LLMClient()
            logger.info("✓ Groq humanizer LLM ready")  # Fix 14: corrected log message
        except Exception as e:
            logger.error(f"Failed to load LLM: {e}")
            self.llm = None

    # ---------------------------------------------------------------------
    # AI Detection
    # ---------------------------------------------------------------------

    def detect_ai(self, text: str) -> dict:
        """Detect AI using both heuristic metrics AND RoBERTa model. Blended."""
        logger.info(f"Detecting AI in text ({len(text)} chars)")

        metrics = compute_metrics(text)
        heuristic = heuristic_ai_score(metrics)
        roberta_score = self._roberta_detect(text)

        # Blend: 70% heuristic (reliable) + 30% RoBERTa
        # Heuristic dominates because RoBERTa is unreliable for modern LLM output.
        raw_blended = heuristic * 0.7 + roberta_score * 0.3
        # Cap to avoid false certainty at the extremes (5%–95%)
        blended = round(max(5.0, min(95.0, raw_blended)))
        confidence = 0.85 if metrics and metrics["word_count"] >= 50 else 0.6

        explanation = self._build_explanation(blended, metrics, heuristic, roberta_score)

        logger.info(f"AI detection: blended={blended}% (heuristic={heuristic}%, roberta={roberta_score:.0f}%)")

        return {
            "ai_percentage": float(blended),
            "confidence": float(confidence),
            "explanation": explanation,
            "metrics": metrics,
            "heuristic_score": heuristic,
            "roberta_score": float(roberta_score),
        }

    def _roberta_detect(self, text: str) -> float:
        """Use RoBERTa detector to get AI probability."""
        if not self.detector_model or not self.detector_tokenizer:
            return 50.0

        try:
            inputs = self.detector_tokenizer(
                text[:2000],
                return_tensors="pt",
                truncation=True,
                max_length=512
            ).to(self.device)

            with torch.no_grad():
                logits = self.detector_model(**inputs).logits

            probs = torch.softmax(logits, dim=-1)
            return probs[0][1].item() * 100
        except Exception as e:
            logger.error(f"RoBERTa detection failed: {e}")
            return 50.0

    def _build_explanation(self, score: int, metrics: dict, heuristic: int, roberta: float) -> str:
        """Build a detailed explanation from metrics."""
        if not metrics:
            return "Unable to analyze text."

        parts = []

        if score > 70:
            parts.append(f"**Verdict:** Likely AI-generated ({score}% probability).")
        elif score > 40:
            parts.append(f"**Verdict:** Mixed signals ({score}% AI probability).")
        else:
            parts.append(f"**Verdict:** Likely human-written ({100-score}% confidence).")

        parts.append(f"\n**Burstiness:** {metrics['burstiness']} " +
                    ("(human-like variance ✓)" if metrics['burstiness'] >= 0.5 else
                     "(too uniform - AI marker ✗)" if metrics['burstiness'] < 0.3 else
                     "(moderate)"))

        parts.append(f"**Lexical Diversity:** {metrics['ttr']} " +
                    ("(rich vocabulary ✓)" if metrics['ttr'] >= 0.6 else
                     "(repetitive - AI marker ✗)" if metrics['ttr'] < 0.45 else
                     "(moderate)"))

        parts.append(f"**Avg Sentence Length:** {metrics['avg_sentence_length']} words " +
                    ("(in AI sweet spot 19-26 ✗)" if 19 <= metrics['avg_sentence_length'] <= 26 else
                     "(outside AI range ✓)"))

        if metrics['human_markers'] > 0:
            markers = []
            if metrics['has_em_dash']: markers.append("em-dashes")
            if metrics['has_parenthetical']: markers.append("parentheticals")
            if metrics['has_contractions']: markers.append("contractions")
            if metrics['starts_with_but_and'] > 0: markers.append("varied sentence starts")
            parts.append(f"**Human markers detected:** {', '.join(markers)} ✓")
        else:
            parts.append("**Human markers:** None detected ✗")

        parts.append(f"\n**Component scores:** Heuristic={heuristic}%, RoBERTa={roberta:.0f}%")

        return "\n".join(parts)

    # ---------------------------------------------------------------------
    # Humanization (iterative until <20%)
    # ---------------------------------------------------------------------

    def humanize(self, text: str) -> dict:
        """Iteratively humanize text until AI score < 20% (or max 3 passes)."""
        if not self.llm:
            return {
                "original_text": text,
                "humanized_text": text,
                "changes_made": "Humanizer not available."
            }

        logger.info(f"Humanizing text ({len(text)} chars), target: <{TARGET_AI_SCORE}%")

        # Get original metrics
        original_metrics = compute_metrics(text)
        original_heuristic = heuristic_ai_score(original_metrics)
        original_roberta = self._roberta_detect(text)
        original_blended = round(max(5.0, min(95.0, original_heuristic * 0.7 + original_roberta * 0.3)))

        best_text = text
        best_score = original_blended
        best_metrics = original_metrics
        all_changes = []
        passes_used = 0

        for attempt in range(1, MAX_HUMANIZATION_PASSES + 1):
            passes_used = attempt
            logger.info(f"Humanization pass {attempt}/{MAX_HUMANIZATION_PASSES}")

            try:
                # Build retry context if not first attempt
                retry_context = ""
                if attempt > 1:
                    retry_context = RETRY_TEMPLATE.format(
                        attempt=attempt,
                        prev_score=best_score,
                        prev_text=best_text[:500]
                    )

                # Generate humanized version
                prompt = HUMANIZE_PROMPT_TEMPLATE.format(
                    text=text,
                    retry_context=retry_context
                )
                raw_response = self.llm.generate(prompt, temperature=0.8 + (attempt * 0.05), max_tokens=2048)

                # Parse response
                humanized_text, changes = self._parse_humanize_response(raw_response, text)

                # Score new version
                new_metrics = compute_metrics(humanized_text)
                new_heuristic = heuristic_ai_score(new_metrics)
                new_roberta = self._roberta_detect(humanized_text)
                new_blended = round(max(5.0, min(95.0, new_heuristic * 0.7 + new_roberta * 0.3)))

                logger.info(f"Pass {attempt}: {original_blended}% -> {new_blended}% (heuristic={new_heuristic}%, roberta={new_roberta:.0f}%)")

                # Track changes
                all_changes.extend(changes)

                # Keep best result
                if new_blended < best_score:
                    best_text = humanized_text
                    best_score = new_blended
                    best_metrics = new_metrics

                # Stop if target reached
                if new_blended <= TARGET_AI_SCORE:
                    logger.info(f"✓ Target reached at pass {attempt}: {new_blended}%")
                    break

            except Exception as e:
                logger.error(f"Pass {attempt} failed: {e}")
                continue

        # Build summary
        target_reached = best_score <= TARGET_AI_SCORE
        changes_summary = self._build_changes_summary(
            original_metrics, best_metrics, original_blended,
            best_score, all_changes, passes_used, target_reached
        )

        return {
            "original_text": text,
            "humanized_text": best_text,
            "changes_made": changes_summary,
            "original_score": original_blended,
            "new_score": best_score,
            "metrics_before": original_metrics,
            "metrics_after": best_metrics,
            "passes_used": passes_used,
            "target_reached": target_reached,
        }

    def _parse_humanize_response(self, raw: str, original: str) -> tuple:
        """Extract humanized text + changes from JSON response."""
        cleaned = raw.replace("```json", "").replace("```", "").strip()

        try:
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON found")

            data = json.loads(cleaned[start:end])
            humanized = data.get("humanized", original)
            changes = data.get("changes", [])
            return humanized, changes
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"JSON parse failed: {e}. Using raw text.")
            return cleaned, ["Rewrite generated"]

    def _build_changes_summary(self, before: dict, after: dict, before_score: int,
                                after_score: int, changes: list, passes: int,
                                target_reached: bool) -> str:
        """Build a detailed summary of changes."""
        if not before or not after:
            return "Text rewritten."

        parts = []

        # Status banner
        if target_reached:
            parts.append(f"✅ **Target reached!** AI score: {before_score}% → **{after_score}%** in {passes} pass{'es' if passes > 1 else ''}")
        else:
            parts.append(f"⚠ **Best result after {passes} passes:** {before_score}% → **{after_score}%** (target was <{TARGET_AI_SCORE}%)")

        # Metric improvements
        parts.append("\n**Metric Changes:**")
        if after["burstiness"] > before["burstiness"]:
            parts.append(f"✓ Burstiness: {before['burstiness']} → {after['burstiness']} (more sentence variety)")
        if after["ttr"] > before["ttr"]:
            parts.append(f"✓ Lexical diversity: {before['ttr']} → {after['ttr']} (richer vocabulary)")
        if after["human_markers"] > before["human_markers"]:
            parts.append(f"✓ Human markers: {before['human_markers']} → {after['human_markers']}")

        # LLM-reported changes
        if changes:
            parts.append("\n**Specific Changes Made:**")
            seen = set()
            for c in changes:
                if c not in seen:
                    parts.append(f"• {c}")
                    seen.add(c)
                if len(seen) >= 6:
                    break

        return "\n".join(parts)
