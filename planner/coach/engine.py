"""Put it together: context + memory + library + playbook -> model -> reply + buttons."""
import logging
import os

from .actions import extract_cards, save_memory, split_reply
from .context import memory_notes, student_context
from .prompt import PLAYBOOK_VERSION, build_system_prompt
from .retrieval import search_library

logger = logging.getLogger(__name__)

MAX_HISTORY = 20
MAX_CHARS = 12000
# Groq's free tier allows about 8000 tokens per minute per model, and a request is counted as
# (input tokens + max_tokens). Keep both parts inside that so a long PDF doesn't get a 413.
MAX_OUTPUT_TOKENS = 1500            # reserved when sizing the input
MIN_OUTPUT_TOKENS = 800
MAX_OUTPUT_TOKENS_CEILING = 3000    # never ask for more than this
TPM_LIMIT = 8000
INPUT_TOKEN_BUDGET = TPM_LIMIT - MAX_OUTPUT_TOKENS - 400   # 400 = safety margin for estimate error
CHARS_PER_TOKEN = 3                                        # pessimistic: maths/LaTeX uses more tokens per character
INPUT_CHAR_BUDGET = INPUT_TOKEN_BUDGET * CHARS_PER_TOKEN
HISTORY_ITEM_CHARS = 2000
TRUNCATION_MARK = "\n\n[... the rest of this text was cut to fit the AI's size limit ...]"
TRUNCATION_NOTE = "\n\n_Note: your text was long, so I only read the first part of it. Send the next section to continue._"
# Tried in order if the configured model is missing or overloaded.
DEFAULT_MODEL = 'openai/gpt-oss-120b'
FALLBACK_MODELS = ['openai/gpt-oss-120b', 'llama-3.3-70b-versatile', 'openai/gpt-oss-20b']


def model_candidates():
    configured = os.environ.get('MODEL_NAME') or os.environ.get('GROQ_MODEL_NAME') or DEFAULT_MODEL
    out = [configured]
    for m in FALLBACK_MODELS:
        if m not in out:
            out.append(m)
    return out


def _clean_history(history):
    out = []
    for item in (history or [])[-MAX_HISTORY:]:
        if not isinstance(item, dict):
            continue
        role = item.get('role')
        content = str(item.get('content', '')).strip()[:MAX_CHARS]
        if role in ('user', 'assistant') and content:
            out.append({'role': role, 'content': content})
    return out


def _build(user, message, history, mode=''):
    """Returns (messages, links, truncated), sized to fit INPUT_CHAR_BUDGET."""
    try:
        library_block, links = search_library(user, message[:MAX_CHARS])
    except Exception:  # retrieval must never break the chat
        logger.exception('Coach library search failed')
        library_block, links = '', []
    truncated = len(message) > MAX_CHARS
    message = message[:MAX_CHARS]
    past = _clean_history(history)

    def size(system, hist):
        return len(system) + sum(len(m['content']) for m in hist) + len(message)

    system = build_system_prompt(
        student_context=student_context(user),
        memory_notes=memory_notes(user),
        library_hits=library_block,
        mode=mode,
    )
    # 1. Too big? Drop the oldest history first.
    while past and size(system, past) > INPUT_CHAR_BUDGET:
        past.pop(0)
    # 2. Still too big (a long attached file)? Use the short system prompt and cap each remaining turn.
    if size(system, past) > INPUT_CHAR_BUDGET:
        system = build_system_prompt(mode=mode, compact=True)
        past = [{'role': m['role'], 'content': m['content'][:HISTORY_ITEM_CHARS]} for m in past]
        while past and size(system, past) > INPUT_CHAR_BUDGET:
            past.pop(0)
    # 3. Still too big? Cut the message itself, and tell the student.
    room = INPUT_CHAR_BUDGET - len(system) - sum(len(m['content']) for m in past)
    if len(message) > room:
        keep = max(room - len(TRUNCATION_MARK), 1000)
        message = message[:keep] + TRUNCATION_MARK
        truncated = True
    return [{'role': 'system', 'content': system}] + past + [{'role': 'user', 'content': message}], links, truncated


def build_messages(user, message, history, mode=''):
    messages, links, _truncated = _build(user, message, history, mode)
    return messages, links


def _is_model_problem(exc):
    text = str(exc).lower()
    status = getattr(exc, 'status_code', None)
    return status in (404, 413, 429, 503) or 'rate_limit' in text or 'request too large' in text or 'model_not_found' in text or 'does not exist' in text or 'decommissioned' in text or 'over capacity' in text


def reply_token_cap(messages):
    """Longest reply we can ask for while (input + reply) stays under the per-minute limit.
    Short chats get long room for worked solutions; a big file gets a shorter reply."""
    est_input = sum(len(m['content']) for m in messages) // CHARS_PER_TOKEN
    return max(MIN_OUTPUT_TOKENS, min(MAX_OUTPUT_TOKENS_CEILING, TPM_LIMIT - 400 - est_input))


def complete(client, messages):
    """Call the first model that works. Returns (text, model_name)."""
    last = None
    for model in model_candidates():
        try:
            resp = client.chat.completions.create(model=model, messages=messages, temperature=0.5, max_tokens=reply_token_cap(messages))
            return (resp.choices[0].message.content or '').strip(), model
        except Exception as exc:  # noqa: BLE001 - we decide below whether to try the next model
            last = exc
            if not _is_model_problem(exc):
                raise
            logger.warning('Coach model %s unavailable (%s); trying next', model, exc)
    raise last


def coach_reply(client, user, message, history=None, mode=''):
    """Returns a dict the chat widget renders."""
    messages, links, truncated = _build(user, message, history, mode)
    raw, model = complete(client, messages)
    clean, tasks, notes = split_reply(raw)
    if truncated and clean:
        clean += TRUNCATION_NOTE
    remembered = save_memory(user, notes) if notes else []
    return {
        'reply': clean or "Sorry, I lost my train of thought. Could you ask that again?",
        'tasks': tasks,
        'cards': extract_cards(clean),
        'remembered': remembered,
        'sources': links,
        'model': model,
        'playbook': PLAYBOOK_VERSION,
    }
