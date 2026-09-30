import json
import logging
import os
import re
import time
from django.core.cache import cache
from groq import Groq

logger = logging.getLogger(__name__)

# Rate limit configuration: 5 requests per 5 minutes per user
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


def _call_groq_with_retry(messages, expected_schema_description, temperature=0.3):
    """
    Calls Groq API, validates strict JSON parsing, and performs exactly 1 auto-retry
    if JSON parsing fails.
    """
    client = get_groq_client()
    model = get_model_name()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        content = response.choices[0].message.content
        return parse_strict_json(content)
    except (json.JSONDecodeError, ValueError) as err:
        logger.warning(f"Initial JSON parse failed: {err}. Retrying with repair prompt...")
        # Auto-retry once with strict repair instruction
        repair_messages = list(messages) + [
            {"role": "assistant", "content": content if 'content' in locals() else ""},
            {
                "role": "user",
                "content": (
                    f"The previous response was not valid JSON. Parse error: {str(err)}. "
                    f"Please re-output the exact data as STRICT, VALID raw JSON only with NO markdown fences, "
                    f"no commentary. Expected schema: {expected_schema_description}"
                )
            }
        ]
        retry_response = client.chat.completions.create(
            model=model,
            messages=repair_messages,
            temperature=0.1,
        )
        retry_content = retry_response.choices[0].message.content
        try:
            return parse_strict_json(retry_content)
        except Exception as retry_err:
            logger.error(f"Retry JSON parse also failed: {retry_err}")
            raise AIProcessingError("Failed to parse structured response from AI after retry. Please try again.")
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        raise AIProcessingError(f"AI service error: {str(e)}")


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

    user_prompt = f"Material Title: {title}\n\nContent:\n{text}"
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

    user_prompt = f"Material Title: {title}\n\nContent:\n{text}"
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

    user_prompt = f"Material Title: {title}\n\nContent:\n{text}"
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
                    c_idx = int(q.get("correct_index", 0))
                    if c_idx < 0 or c_idx >= len(opts):
                        c_idx = 0
                except (ValueError, TypeError):
                    c_idx = 0

                valid_questions.append({
                    "question": str(q["question"]).strip(),
                    "options": opts,
                    "correct_index": c_idx,
                    "explanation": str(q.get("explanation", "Correct answer based on the document.")).strip()
                })

    if not valid_questions:
        raise AIProcessingError("Could not generate a valid quiz from the provided document.")
    return valid_questions
