"""API providers MWB can send language work to (design §12). The defaults follow AI-App's PROVIDERS list
(src/renderer/app.js), so the same key works in both apps. Groq is the only one wired up in Phase 0;
the router adds the others in Phase 3."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    base: str               # OpenAI-compatible base URL
    model: str              # notes, email, code and the journal
    quick_model: str        # short jobs: labels, small rewrites
    key_page: str           # where you create a key
    key_prefix: str = ''    # how this provider's keys start, for a friendlier error


GROQ = Provider('groq', 'Groq', 'https://api.groq.com/openai/v1', 'openai/gpt-oss-120b', 'openai/gpt-oss-20b',
                'https://console.groq.com/keys', 'gsk_')

PROVIDERS = {GROQ.id: GROQ}
