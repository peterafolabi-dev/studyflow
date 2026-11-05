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


def build_messages(user, message, history, mode=''):
    try:
        library_block, links = search_library(user, message)
    except Exception:  # retrieval must never break the chat
        logger.exception('Coach library search failed')
        library_block, links = '', []
    system = build_system_prompt(
        student_context=student_context(user),
        memory_notes=memory_notes(user),
        library_hits=library_block,
        mode=mode,
    )
    messages = [{'role': 'system', 'content': system}]
    for item in (history or [])[-MAX_HISTORY:]:
        if not isinstance(item, dict):
            continue
        role = item.get('role')
        content = str(item.get('content', '')).strip()[:MAX_CHARS]
        if role in ('user', 'assistant') and content:
            messages.append({'role': role, 'content': content})
    messages.append({'role': 'user', 'content': message[:MAX_CHARS]})
    return messages, links


def _is_model_problem(exc):
    text = str(exc).lower()
    status = getattr(exc, 'status_code', None)
    return status in (404, 429, 503) or 'model_not_found' in text or 'does not exist' in text or 'decommissioned' in text or 'over capacity' in text


def complete(client, messages):
    """Call the first model that works. Returns (text, model_name)."""
    last = None
    for model in model_candidates():
        try:
            resp = client.chat.completions.create(model=model, messages=messages, temperature=0.5, max_tokens=3000)
            return (resp.choices[0].message.content or '').strip(), model
        except Exception as exc:  # noqa: BLE001 - we decide below whether to try the next model
            last = exc
            if not _is_model_problem(exc):
                raise
            logger.warning('Coach model %s unavailable (%s); trying next', model, exc)
    raise last


def coach_reply(client, user, message, history=None, mode=''):
    """Returns a dict the chat widget renders."""
    messages, links = build_messages(user, message, history, mode)
    raw, model = complete(client, messages)
    clean, tasks, notes = split_reply(raw)
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
