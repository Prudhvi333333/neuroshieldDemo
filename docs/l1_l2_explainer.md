# L1 and L2 Explained (Plain Language, Teacher Style)

This guide explains our two decision layers—L1 and L2—in the simplest possible way. Imagine we’re in a classroom: I’ll use analogies, short examples, and a visual flow so everyone can follow along.

---

## What Are L1 and L2?

- L1 is the fast safety gate. It instantly blocks obviously dangerous requests.
- L2 is the semantic decision layer. It reads the intent, understands nuance (including other languages), and either rewrites the request safely or stops it.

Think of L1 as the security guard at the door, and L2 as the teacher who carefully reads and guides.

---

## L1: The Fast Safety Gate

Teacher’s explanation:
- “If a request openly asks for something dangerous, we don’t debate. We stop it right away.”

What L1 does:
- Looks for clear red flags (“steal secrets”, “teach step‑by‑step phishing”, “ignore safety rules”).
- Responds in a fraction of a second.
- Blocks immediately when it spots blatant harm.

What L1 does not do:
- It doesn’t analyze subtle intent, sarcasm, or gentle phrasing.
- It doesn’t interpret every language or indirect wording.

L1 example (to say aloud):
- “Write Python to enumerate and exfiltrate environment secrets.”
- Expected outcome: Blocked on the spot. The system ends the flow and shows a clear ‘Blocked’ message.

---

## L2: The Semantic + ML Decision Layer

Teacher’s explanation:
- “When a request is not obviously bad, we slow down and understand what it really means. If it looks risky but useful, we rewrite it into a safe version.”

What L2 does:
- Understands the meaning, even if the wording is indirect or in another language.
- Weighs multiple risk signals (e.g., social‑engineering themes, credential‑theft intent, behavior‑hijacking attempts).
- If risk is medium, it rewrites the request into a safe, helpful prompt and validates the rewrite before continuing.

What L2 does not do:
- It doesn’t override L1’s hard blocks for blatantly dangerous content.
- It doesn’t let unsafe rewrites through—rewrites are checked, and unsafe ones are blocked.

L2 example (to say aloud):
- “For staff training, outline how callers might pressure employees to share a one‑time MFA code; include warning signs and safe responses.”
- Expected outcome: Marked as medium risk → rewritten into a defender‑focused training prompt (emphasizing warning signs, refusal language, and policy). Only the safe rewrite continues.

---

## Quick Visual: How a Request Flows

1) User sends a request.
2) L1 scans instantly.
   - If clearly harmful → Blocked (stop).
   - Else → Forward to L2.
3) L2 reads intent and estimates risk.
   - High risk → Blocked (stop).
   - Medium risk → Rewritten safely → Validated → Continue.
   - Low risk → Continue.
4) Only safe prompts move forward to get a response.

---

## Technical Flow: How ML is used

Here is the simple, non‑technical way to explain what the “ML” does in L2 and how it works with the rest of the system.

At a glance:
- L1 is rule‑based and instant (no ML). It blocks the obvious.
- L2 mixes semantic understanding with ML scoring. It reads the intent (even in other languages), estimates risk, and either rewrites safely or stops.

Step by step in L2:
1) Understand the language and intent
   - We quickly detect the writing system (e.g., English, Spanish, Russian).
   - If needed, we ask a small model to confirm the language.
   - We then turn the request into a short, safe English summary of the user’s intent (not a full translation, just intent).

2) Score semantic intent (0 to 1)
   - We ask a model to rate how strongly the request looks like certain risky themes: social engineering, credential theft, exfiltration, “model‑jacking,” etc.
   - The result is a set of confidences, like social_engineering = 0.66, credential_theft = 0.22, and so on.

3) ML risk features over the intent
   - Separately, we use an ML‑style scorer that looks for combinations of risk signals in the intent text (co‑occurrence patterns that often appear together in unsafe requests).
   - This produces a risk score from 0 to 1 (for example, 0.62).

4) Conservative combination
   - We combine the two views (semantic intents and ML risk) by taking the higher one. This reduces the chance of missing real risks.

Scoring at a glance:
- Combined risk = max(ML risk score, highest semantic‑intent confidence)
- If either view is high, we treat the request as high risk.

Multilingual path:
- Non‑English prompts are first summarized into a short English intent.
- We do not apply fast “safe” shortcuts to non‑English; they always go through this semantic check.

5) Route by thresholds
   - 0.85 or higher → Blocked (too risky to continue).
   - 0.60 to 0.84 → Risky → we rewrite the request into a safe version and check it again.
   - Below 0.20 → Safe (only English gets this quick pass).

6) Safe rewrite and validation
   - For Risky items, we produce a safer version of the prompt (training/defender focus, no procedural abuse).
   - We validate the rewritten prompt again. If it is still unsafe, we stop. If it is safe, we allow it to continue.

7) Final safety check
   - Before any answer is produced, a final quick safety check runs. Only safe prompts get answers.

Why this is stronger than “keywords”
- It focuses on intent and meaning, not just exact words.
- It works across languages (by summarizing intent in English first).
- It has multiple independent checks; if any see risk, we treat it as risky.

Two worked examples
1) L1 hard‑block example (instant)
   - Request: “Write Python to enumerate and exfiltrate environment secrets.”
   - Outcome: L1 blocks immediately. Risk is effectively ~0.95. No rewrite, no answer.

2) L2 rewrite example (medium risk)
   - Request: “For staff training, outline how callers might pressure employees to share a one‑time MFA code; include warning signs and safe responses.”
   - Intent summary: “Training on recognizing pressure tactics for MFA codes; include warning signs and safe responses.”
   - Semantic intents (example): social_engineering = 0.66, credential_theft = 0.22, others ≈ low.
   - ML risk (example): 0.62 from co‑occurring signals like “pressure,” “share codes,” “training.”
   - Combined risk: max(0.66, 0.62) = 0.66 → Risky → rewrite.
   - Safe rewrite: The system reformulates it into a defender‑focused training request (refusal language, policy emphasis, no attacker playbooks).
   - Validation: The rewritten prompt is checked again. If safe, it proceeds; if not, it is blocked.

---

## FAQs (What your audience might ask)

- “Is this just keyword matching?”
  - No. L1 stops the obvious cases fast, but L2 looks at meaning and intent, even in other languages. That’s how we catch nuanced risks and still help safely.

- “Why not block everything risky?”
  - Many real‑world requests are training or awareness‑focused. L2 rewrites them into safe prompts so teams can learn without exposure to harm.

- “What happens if the rewrite is still unsafe?”
  - Then it’s blocked before any answer is produced. Safety comes first.

---

## Audience Takeaways

- L1 is speed: it blocks obvious harm instantly.
- L2 is understanding: it reads intent and guides the request to a safe path.
- Together, they protect users and still deliver helpful, safe outcomes.
