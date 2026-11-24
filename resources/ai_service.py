import json
import logging
import os
import re
import time
from django.core.cache import cache
from groq import Groq

logger = logging.getLogger(__name__)

# Rate limit configuration: 6 requests per 5 minutes per user
RATE_LIMIT_MAX_REQUESTS = 6
RATE_LIMIT_WINDOW_SECONDS = 300


class RateLimitExceeded(Exception):
    def __init__(self, retry_after):
        self.retry_after = retry_after
        super().__init__(f"Rate limit reached. Please wait {retry_after} seconds before making another AI request.")


class AIProcessingError(Exception):
    pass


def check_and_increment_rate_limit(user_id, bucket='pdf_ai', max_requests=RATE_LIMIT_MAX_REQUESTS, window=RATE_LIMIT_WINDOW_SECONDS):
    """
    Enforces per-user rate limiting using Django cache.
    Returns remaining requests count or raises RateLimitExceeded.
    """
    cache_key = f"rl_{bucket}_{user_id}"
    now = time.time()
    
    history = cache.get(cache_key) or []
    # Filter out timestamps outside the active window
    history = [ts for ts in history if now - ts < window]

    if len(history) >= max_requests:
        oldest = history[0]
        retry_after = max(1, int(window - (now - oldest)))
        raise RateLimitExceeded(retry_after)

    history.append(now)
    cache.set(cache_key, history, timeout=window)
    return max_requests - len(history)


def get_groq_client():
    api_key = os.environ.get('GROQ_API_KEY')
    if not api_key:
        raise AIProcessingError("GROQ_API_KEY is not configured on the server.")
    return Groq(api_key=api_key)


def get_model_name():
    return os.environ.get('MODEL_NAME') or os.environ.get('GROQ_MODEL_NAME') or 'openai/gpt-oss-20b'


def parse_strict_json(raw_text):
    """
    Safely cleans and extracts valid JSON from model responses,
    handling codeblocks like ```json ... ``` and leading/trailing chatter.
    """
    if not raw_text:
        raise ValueError("Empty response received.")

    cleaned = raw_text.strip()
    # Strip markdown codeblocks if present
    fence_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    # Find first '{' or '[' and last '}' or ']'
    start_bracket = re.search(r'[{\[]', cleaned)
    if start_bracket:
        start_idx = start_bracket.start()
        end_idx = max(cleaned.rfind('}'), cleaned.rfind(']'))
        if end_idx != -1 and end_idx >= start_idx:
            cleaned = cleaned[start_idx:end_idx + 1]

    return json.loads(cleaned)


# Groq's free tier allows ~8000 tokens/minute per model and counts (input + max_tokens), so size both.
AI_MAX_OUTPUT_TOKENS = 2500
AI_MAX_INPUT_CHARS = 9000
AI_FALLBACK_MODELS = ['openai/gpt-oss-20b', 'openai/gpt-oss-120b', 'llama-3.3-70b-versatile']
FRIENDLY_BUSY = "The AI is busy right now (free-tier limit). Please wait a minute and try again."


def _model_candidates():
    out = [get_model_name()]
    for m in AI_FALLBACK_MODELS:
        if m not in out:
            out.append(m)
    return out


def _is_model_problem(exc):
    text = str(exc).lower()
    status = getattr(exc, 'status_code', None)
    return (status in (404, 413, 429, 503) or 'rate_limit' in text or 'request too large' in text
            or 'model_not_found' in text or 'does not exist' in text or 'decommissioned' in text
            or 'over capacity' in text)


def _chat(client, messages, temperature, max_tokens=None):
    """Call the first model that works (limits and outages happen on the free tier)."""
    last = None
    for model in _model_candidates():
        kwargs = dict(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens or AI_MAX_OUTPUT_TOKENS)
        if 'gpt-oss' in model:
            kwargs['reasoning_effort'] = 'low'  # keep thinking short so the JSON isn't cut off
        try:
            return client.chat.completions.create(**kwargs).choices[0].message.content
        except Exception as exc:  # noqa: BLE001 - decide below whether to try the next model
            last = exc
            if not _is_model_problem(exc):
                raise
            logger.warning('AI model %s unavailable (%s); trying next', model, exc)
    raise last


def _clip(text):
    text = text or ''
    if len(text) > AI_MAX_INPUT_CHARS:
        return text[:AI_MAX_INPUT_CHARS] + '\n\n[... rest of the document was cut to fit the AI size limit ...]'
    return text


def _call_groq_with_retry(messages, expected_schema_description, temperature=0.3):
    """
    Calls Groq (with model fallback), parses strict JSON, and retries once if the JSON is broken.
    Always raises AIProcessingError with a message a student can read.
    """
    client = get_groq_client()
    content = ''
    try:
        content = _chat(client, messages, temperature)
        return parse_strict_json(content)
    except (json.JSONDecodeError, ValueError) as err:
        logger.warning(f"Initial JSON parse failed: {err}. Retrying with repair prompt...")
        repair_messages = list(messages) + [
            {"role": "assistant", "content": content or ""},
            {
                "role": "user",
                "content": (
                    f"The previous response was not valid JSON. Parse error: {str(err)}. "
                    f"Please re-output the exact data as STRICT, VALID raw JSON only with NO markdown fences, "
                    f"no commentary. Expected schema: {expected_schema_description}"
                )
            }
        ]
        try:
            return parse_strict_json(_chat(client, repair_messages, 0.1))
        except Exception as retry_err:  # noqa: BLE001
            logger.error(f"Retry failed: {retry_err}")
            if _is_model_problem(retry_err):
                raise AIProcessingError(FRIENDLY_BUSY)
            raise AIProcessingError("The AI gave an unreadable answer. Please try again.")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Groq API error: {e}")
        if _is_model_problem(e):
            raise AIProcessingError(FRIENDLY_BUSY)
        raise AIProcessingError("The AI service had a problem. Please try again in a moment.")


def summarize_material(text, title="Study Material"):
    """
    Generates a structured summary with high-yield key takeaways.
    Returns: {"summary": str, "key_points": [str]}
    """
    system_prompt = (
        "You are an expert university study coach. Analyze the provided study material and return "
        "a concise, high-impact summary and bulleted key points. "
        "You MUST return strictly valid JSON matching this schema:\n"
        "{\n"
        '  "summary": "2-3 concise paragraphs summarizing core themes and objectives.",\n'
        '  "key_points": ["Key takeaway 1", "Key takeaway 2", "Key takeaway 3", ...]\n'
        "}\n"
        "Return ONLY the raw JSON object. Do not include markdown ticks or outside text."
    )

    user_prompt = f"Material Title: {title}\n\nContent:\n{_clip(text)}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    schema_desc = '{"summary": "...", "key_points": ["...", "..."]}'
    data = _call_groq_with_retry(messages, schema_desc, temperature=0.3)
    
    # Ensure standard dictionary keys
    summary = data.get("summary", "")
    key_points = data.get("key_points", [])
    if isinstance(key_points, str):
        key_points = [k.strip() for k in key_points.split("\n") if k.strip()]
    return {"summary": summary, "key_points": key_points}


def generate_flashcards_from_material(text, title="Study Material", card_count=8):
    """
    Generates high-yield flashcards with front (question/concept) and back (answer/explanation).
    Returns: [{"front": str, "back": str}]
    """
    system_prompt = (
        "You are an academic flashcard creator. Extract the most important testable concepts, "
        "definitions, formulas, and insights from the document.\n"
        f"Generate {card_count} flashcards as strictly valid JSON matching this schema:\n"
        "{\n"
        '  "flashcards": [\n'
        '    {"front": "Clear question or concept prompt", "back": "Precise explanation or answer"}\n'
        '  ]\n'
        "}\n"
        "Return ONLY the raw JSON object. Do not include markdown codeblocks or other commentary."
    )

    user_prompt = f"Material Title: {title}\n\nContent:\n{_clip(text)}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    schema_desc = '{"flashcards": [{"front": "...", "back": "..."}]}'
    data = _call_groq_with_retry(messages, schema_desc, temperature=0.3)
    
    cards = data.get("flashcards", [])
    valid_cards = []
    for c in cards:
        if isinstance(c, dict) and c.get("front") and c.get("back"):
            valid_cards.append({
                "front": str(c["front"]).strip(),
                "back": str(c["back"]).strip()
            })
    
    if not valid_cards:
        raise AIProcessingError("The AI did not produce any valid flashcards from this text.")
    return valid_cards


def generate_quiz_from_material(text, title="Study Material", question_count=5):
    """
    Generates 5-10 multiple-choice questions with 4 options each, correct index, and explanation.
    Returns: [{"question": str, "options": [str], "correct_index": int, "explanation": str}]
    """
    system_prompt = (
        "You are an expert exam author. Design a comprehensive practice quiz based on the material.\n"
        f"Create exactly {question_count} challenging, university-level multiple-choice questions.\n"
        "You MUST return strictly valid JSON matching this schema:\n"
        "{\n"
        '  "questions": [\n'
        '    {\n'
        '      "question": "Question stem",\n'
        '      "options": ["A) First option", "B) Second option", "C) Third option", "D) Fourth option"],\n'
        '      "correct_index": 0,\n'
        '      "explanation": "Clear explanation of why this answer is correct and others are wrong."\n'
        '    }\n'
        '  ]\n'
        "}\n"
        "Note: correct_index must be an integer (0, 1, 2, or 3) corresponding to the correct option index.\n"
        "Return ONLY the raw JSON object with NO surrounding markdown or notes."
    )

    user_prompt = f"Material Title: {title}\n\nContent:\n{_clip(text)}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    schema_desc = '{"questions": [{"question": "...", "options": ["..."], "correct_index": 0, "explanation": "..."}]}'
    data = _call_groq_with_retry(messages, schema_desc, temperature=0.3)

    raw_questions = data.get("questions", [])
    valid_questions = []
    for q in raw_questions:
        if isinstance(q, dict) and q.get("question") and isinstance(q.get("options"), list):
            opts = [str(o).strip() for o in q["options"] if str(o).strip()]
            if len(opts) >= 2:
                try:
                    c_idx = int(q.get("correct_index"))
                except (ValueError, TypeError):
                    continue  # no usable answer key: skip rather than mark option A correct
                if c_idx < 0 or c_idx >= len(opts):
                    continue

                valid_questions.append({
                    "question": str(q["question"]).strip(),
                    "options": opts,
                    "correct_index": c_idx,
                    "explanation": str(q.get("explanation", "Correct answer based on the document.")).strip()
                })

    if not valid_questions:
        raise AIProcessingError("Could not generate a valid quiz from the provided document.")
    return valid_questions


def generate_cbt_bank_from_pdf(text, title="Past Question", count=10, time_limit_minutes=15):
    """
    Extracts or synthesizes CBT exam questions from past questions or course materials.
    """
    system_prompt = (
        "You are an expert Nigerian university examination coordinator and CBT test author. "
        "Analyze the provided document (past questions or lecture materials) and construct "
        f"a realistic, standardized CBT practice test of {count} questions.\n"
        "If the document already contains past questions with options, extract and clean them faithfully. "
        "If it contains notes or study topics without explicit questions, create high-yield multiple-choice test questions "
        "covering the core concepts.\n\n"
        "You MUST return strictly valid JSON matching this schema:\n"
        "{\n"
        '  "title": "Short title, e.g. MTH101 2022/2023 CBT Practice",\n'
        f'  "time_limit_minutes": {time_limit_minutes},\n'
        '  "questions": [\n'
        '    {\n'
        '      "question": "Question text here",\n'
        '      "option_a": "First choice",\n'
        '      "option_b": "Second choice",\n'
        '      "option_c": "Third choice",\n'
        '      "option_d": "Fourth choice",\n'
        '      "correct_option": "A",\n'
        '      "explanation": "Clear breakdown of why this option is correct and why the alternatives are incorrect."\n'
        '    }\n'
        '  ]\n'
        "}\n"
        "Note: correct_option MUST be exactly one of 'A', 'B', 'C', or 'D'.\n"
        "Return ONLY the raw JSON object with NO surrounding markdown or extra commentary."
    )

    user_prompt = f"Document Title: {title}\n\nDocument Text:\n{_clip(text)}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    schema_desc = '{"title": "...", "time_limit_minutes": 15, "questions": [{"question": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A", "explanation": "..."}]}'
    data = _call_groq_with_retry(messages, schema_desc, temperature=0.2)

    raw_questions = data.get("questions", [])
    valid_questions = []
    for q in raw_questions:
        if isinstance(q, dict) and q.get("question"):
            oa = str(q.get("option_a", "")).strip()
            ob = str(q.get("option_b", "")).strip()
            oc = str(q.get("option_c", "")).strip()
            od = str(q.get("option_d", "")).strip()
            c_opt = str(q.get("correct_option", "A")).strip().upper()
            if c_opt not in ['A', 'B', 'C', 'D']:
                c_opt = 'A'

            if oa and ob:
                valid_questions.append({
                    "question": str(q["question"]).strip(),
                    "option_a": oa,
                    "option_b": ob,
                    "option_c": oc or "None of the above",
                    "option_d": od or "All of the above",
                    "correct_option": c_opt,
                    "explanation": str(q.get("explanation", "Standard answer according to syllabus.")).strip()
                })

    if not valid_questions:
        raise AIProcessingError("Could not generate valid CBT questions from this document.")

    res_title = str(data.get("title") or f"{title} CBT Practice").strip()
    try:
        t_limit = int(data.get("time_limit_minutes", time_limit_minutes))
    except (ValueError, TypeError):
        t_limit = time_limit_minutes

    return {
        "title": res_title,
        "time_limit_minutes": max(5, min(120, t_limit)),
        "questions": valid_questions
    }


def explain_cbt_answer_with_ai(question_text, option_a, option_b, option_c, option_d, user_choice, correct_choice, base_explanation=""):
    """
    Asks the AI Study Coach for a personalized, clear explanation of a test question.
    """
    client = get_groq_client()

    options_formatted = f"A) {option_a}\nB) {option_b}\nC) {option_c}\nD) {option_d}"
    prompt = (
        f"A student took a CBT exam and wants your help understanding this question:\n\n"
        f"Question:\n{question_text}\n\n"
        f"Options:\n{options_formatted}\n\n"
        f"The student selected: Option {user_choice or 'None (skipped)'}\n"
        f"The correct answer is: Option {correct_choice}\n"
    )
    if base_explanation:
        prompt += f"Preliminary note: {base_explanation}\n"

    system_prompt = (
        "You are StudyFlow's encouraging, expert university AI Study Coach. "
        "Explain step-by-step why the correct option is indeed correct, and briefly explain "
        "where the misconception lies if the student chose the wrong option. "
        "Write in a warm, motivating tone. Use LaTeX ($...$) for mathematical formulas. "
        "Keep your entire answer concise, formatted with clear bullets or short paragraphs (under 160 words)."
    )

    try:
        reply = _chat(client, [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ], 0.4, max_tokens=600)
        return (reply or '').strip() or base_explanation
    except Exception as e:
        logger.error(f"Error fetching AI explanation: {e}")
        return base_explanation or "The correct option is derived from standard syllabus principles."
