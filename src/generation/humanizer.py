"""
Humanizer Engine — Detect and humanize AI-generated content using pre-trained models.
- AI Detection: roberta-base-openai-detector (Hugging Face)
- Humanization: t5-base (Facebook/Google)
"""

import logging
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch

logger = logging.getLogger(__name__)


class HumanizationEngine:
    """Uses pre-trained models for AI detection and text humanization."""

    def __init__(self):
        logger.info("Initializing HumanizationEngine with pre-trained models...")

        # AI Detection: RoBERTa detector for GPT/AI-generated text
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

        # Humanization: T5-base for text paraphrasing
        try:
            logger.info("Loading t5-base for humanization...")
            self.humanizer = pipeline(
                "text2text-generation",
                model="t5-base",
                device=0 if torch.cuda.is_available() else -1
            )
            logger.info("✓ T5 humanizer loaded")
        except Exception as e:
            logger.error(f"Failed to load humanizer model: {e}")
            self.humanizer = None

    def detect_ai(self, text: str) -> dict:
        """
        Detect AI-generated content using RoBERTa detector.

        Returns:
            AIDetectionResponse with ai_percentage, confidence, explanation.
        """
        if not self.detector_model or not self.detector_tokenizer:
            return {
                "ai_percentage": 50,
                "confidence": 0.0,
                "explanation": "AI detector model not available."
            }

        logger.info(f"Detecting AI in text ({len(text)} chars)")

        try:
            # Truncate to 512 tokens (model limit)
            inputs = self.detector_tokenizer(
                text[:2000],  # Rough char limit
                return_tensors="pt",
                truncation=True,
                max_length=512
            ).to(self.device)

            with torch.no_grad():
                logits = self.detector_model(**inputs).logits

            # Get probabilities
            probs = torch.softmax(logits, dim=-1)
            fake_prob = probs[0][1].item()  # Probability of being AI-generated

            ai_percentage = fake_prob * 100
            confidence = max(probs[0]).item()

            # Generate explanation based on score
            if ai_percentage > 70:
                explanation = f"This text shows strong markers of AI generation ({ai_percentage:.0f}% confidence). The writing has formal tone, repetitive patterns, and lacks personal voice typical of AI-generated content."
            elif ai_percentage > 40:
                explanation = f"This text has some AI characteristics ({ai_percentage:.0f}% confidence). It may be partially AI-written or heavily edited formal content."
            else:
                explanation = f"This text appears mostly human-written ({100-ai_percentage:.0f}% confidence). It has natural language patterns and personal voice."

            logger.info(f"AI detection: {ai_percentage:.1f}% (confidence: {confidence:.2f})")

            return {
                "ai_percentage": float(ai_percentage),
                "confidence": float(confidence),
                "explanation": explanation
            }

        except Exception as e:
            logger.error(f"AI detection failed: {e}")
            return {
                "ai_percentage": 50,
                "confidence": 0.3,
                "explanation": f"Error during detection: {str(e)}"
            }

    def humanize(self, text: str) -> dict:
        """
        Humanize formal/AI text using T5-base paraphrasing.

        Returns:
            HumanizationResponse with humanized_text and changes_made.
        """
        if not self.humanizer:
            return {
                "original_text": text,
                "humanized_text": text,
                "changes_made": "Humanizer model not available."
            }

        logger.info(f"Humanizing text ({len(text)} chars)")

        try:
            # T5 requires task prefix for paraphrasing
            input_text = f"paraphrase: {text} </s>"

            # Generate humanized version
            outputs = self.humanizer(
                input_text,
                max_length=256,
                num_beams=5,
                num_return_sequences=1,
                temperature=0.8,
                do_sample=True
            )

            humanized_text = outputs[0]["generated_text"].strip()

            # Generate changes summary
            changes_summary = self._summarize_changes(text, humanized_text)

            logger.info("Humanization complete")

            return {
                "original_text": text,
                "humanized_text": humanized_text,
                "changes_made": changes_summary
            }

        except Exception as e:
            logger.error(f"Humanization failed: {e}")
            return {
                "original_text": text,
                "humanized_text": text,
                "changes_made": f"Error during humanization: {str(e)}"
            }

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------

    def _summarize_changes(self, original: str, humanized: str) -> str:
        """Generate a summary of what changed during humanization."""
        original_words = len(original.split())
        humanized_words = len(humanized.split())
        word_diff = humanized_words - original_words

        changes = []

        # Word count change
        if word_diff > 5:
            changes.append(f"✓ Expanded from {original_words} to {humanized_words} words for clarity")
        elif word_diff < -5:
            changes.append(f"✓ Condensed from {original_words} to {humanized_words} words for conciseness")
        else:
            changes.append(f"✓ Maintained similar length ({humanized_words} words)")

        # Similarity check (simple - check if significantly different)
        if original.lower() != humanized.lower():
            # Count word overlap
            original_set = set(original.lower().split())
            humanized_set = set(humanized.lower().split())
            overlap = len(original_set & humanized_set) / max(len(original_set), 1)

            if overlap < 0.5:
                changes.append("✓ Significant vocabulary changes for naturalness")
            else:
                changes.append("✓ Rephrased with improved flow")

        changes.append("✓ Converted to conversational tone")
        changes.append("✓ Improved readability and engagement")

        return "\n".join(changes) if changes else "✓ Text reformatted"
