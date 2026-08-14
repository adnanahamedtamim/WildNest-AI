"""WildNest AI — per-pet chat assistant powered by Groq.

The model is given the specific animal's full profile + a summary of its
environmental analytics as context, so answers are personalised to THAT animal.
It also draws on the model's general knowledge of animal care, supplemented by a
local RAG layer (rag.py) that retrieves and cites species care references —
strictly secondary to the pet's own real, logged data (see build_system_context).
"""
import os
import re
import json
import base64
import statistics
from datetime import datetime

TEXT_MODEL = 'llama-3.3-70b-versatile'
VISION_MODEL = 'qwen/qwen3.6-27b'

# ---- lazy Groq client -------------------------------------------------------

_client = None


def _get_api_key():
    return os.getenv('GROQ_API_KEY', '').strip()


def is_configured():
    key = _get_api_key()
    return bool(key) and key != 'PASTE_YOUR_NEW_KEY_HERE'


def _get_client():
    global _client
    if _client is None:
        from groq import Groq
        _client = Groq(api_key=_get_api_key())
    return _client


# ---- context building ------------------------------------------------------

def _fmt(value, suffix=''):
    return f'{value}{suffix}' if value is not None else 'not recorded'


def build_analytics_summary(logs):
    """Turn environmental logs into a compact text summary for the model."""
    if not logs:
        return 'No environmental data has been logged yet.'

    def col(attr):
        return [getattr(l, attr) for l in logs if getattr(l, attr) is not None]

    lines = [f'Total logged entries: {len(logs)}.']
    first, last = logs[0].timestamp, logs[-1].timestamp
    lines.append(f'Data spans {first.strftime("%b %d, %Y")} to {last.strftime("%b %d, %Y")}.')

    def describe(attr, label, unit=''):
        vals = col(attr)
        if not vals:
            return
        avg = round(statistics.mean(vals), 1)
        line = f'{label}: avg {avg}{unit}, range {min(vals)}{unit}–{max(vals)}{unit}'
        if len(vals) >= 2:
            trend = vals[-1] - vals[0]
            direction = 'rising' if trend > 0 else ('falling' if trend < 0 else 'stable')
            line += f', latest {vals[-1]}{unit} ({direction})'
        lines.append(line)

    describe('temperature_f', 'Temperature', '°F')
    describe('humidity_pct', 'Humidity', '%')
    describe('lighting_hours', 'Lighting', ' hrs')
    describe('feeding_amount_g', 'Feeding', 'g')
    describe('weight_g', 'Weight', 'g')
    describe('stress_level', 'Stress (1-5)')
    describe('activity_level', 'Activity (1-5)')

    recent_notes = [l.notes for l in logs[-3:] if l.notes]
    if recent_notes:
        lines.append('Recent caretaker notes: ' + ' | '.join(recent_notes))

    return '\n'.join(lines)


def build_medical_summary(records):
    """Turn dynamic medical records into a compact text summary for the model."""
    if not records:
        return 'No medical records logged yet.'
    lines = []
    for r in records[:8]:  # most recent first, cap to keep the prompt lean
        line = f"{r.record_date.strftime('%b %d, %Y')} — {r.title}"
        if r.vet_name:
            line += f" (seen by {r.vet_name})"
        if r.treatment:
            line += f". Treatment: {r.treatment}"
        if r.notes:
            line += f". Notes: {r.notes}"
        lines.append(line)
    return '\n'.join(lines)


def build_system_context(animal, query=''):
    """Full personalised instruction for the model about this specific animal.

    query: the caretaker's actual question (or a synthetic topic string for
    non-chat callers like the meal planner) — used ONLY to fetch more relevant
    RAG reference chunks. It never changes what pet data is included; the
    pet's own profile/medical/analytics are always present in full."""
    a = animal
    analytics = build_analytics_summary(list(a.env_logs))
    medical = build_medical_summary(list(a.medical_records))

    handover_line = f"Days since handover to current owner: {a.days_since_handover}" if a.handover_date else ""

    meal_plan_block = ""
    if (a.meal_plan_content and a.meal_plan_generated_at
            and a.meal_plan_generated_at.date() == datetime.utcnow().date()):
        meal_plan_block = (
            "=== TODAY'S GENERATED MEAL PLAN (already shown to the caretaker — "
            "refer back to it rather than repeating or contradicting it) ===\n"
            f"{a.meal_plan_content}"
        )

    # RAG: supplementary species reference — SECONDARY to the pet's own data above,
    # used only to fill gaps or add general context, and always citable when used
    rag_block = ""
    import rag
    rag_chunks = rag.retrieve(a.species, query, k=4)
    if rag_chunks:
        formatted = '\n\n'.join(
            f"[{rag.pretty_source(c['source'])}]\n{c['text']}" for c in rag_chunks
        )
        rag_block = f"""
=== SUPPLEMENTARY SPECIES REFERENCE (secondary source — see rules below) ===
{formatted}"""

    return f"""You are WildNest, a warm, knowledgeable assistant that helps caretakers
look after their specific rescued or exotic pet. You are speaking with the
current caretaker of the pet described below.
Refer to it as "your pet" or by its name — never call it "the animal".

=== THIS PET'S PROFILE (mandatory — always ground your answer in this) ===
Name: {a.name}
Species: {a.species}{(' (' + a.common_name + ')') if a.common_name else ''}
Age: {_fmt(a.age_years, ' years')}
Sex: {_fmt(a.sex)}
Origin: {a.origin} ({'currently listed for rehoming' if a.status == 'listed' else 'in care' if a.status == 'in_care' else a.status.replace('_', ' ')})
Current location: {_fmt(a.current_location)}
Rescue date: {a.rescue_date.strftime('%B %d, %Y') if a.rescue_date else 'not recorded'}
Rescue location: {_fmt(a.rescue_location)}
Known stress triggers: {_fmt(a.stress_triggers)}
Dietary requirements: {_fmt(a.dietary_requirements)}
Background: {_fmt(a.rescue_reason)}
{handover_line}

=== THIS PET'S MEDICAL HISTORY (mandatory, most recent first) ===
{medical}

=== THIS PET'S LOGGED ANALYTICS — temperature, humidity, weight, feeding, stress, activity (mandatory) ===
{analytics}
{meal_plan_block}
{rag_block}

=== HOW TO RESPOND ===
- MANDATORY: always ground your answer first in THIS pet's own profile, medical
  history, and logged analytics above — especially its actual temperature,
  humidity, weight, feeding, and behaviour data. Never skip or ignore this,
  even when reference material is also available below.
- The supplementary species reference above (if present) is SECONDARY: use it
  only to add general species knowledge or fill in gaps this pet's own records
  don't cover. It must NEVER override, contradict, or take priority over this
  pet's own real, logged data — if the two ever conflict, this pet's own data
  always wins.
- If you draw a specific fact from the supplementary reference, briefly cite it
  in parentheses, e.g. (Source: Sulcata Tortoise Care Reference). Don't cite
  anything you didn't actually use from it.
- Be concise, friendly, and practical. Use short paragraphs or bullet points.
- If something suggests a possible health emergency, clearly advise contacting a
  veterinarian — you assist, you do not replace professional veterinary care.
- If data is missing, say so and suggest what the caretaker could start logging."""


# ---- shared call/error handling ---------------------------------------------

def _friendly_error(e):
    msg = str(e)
    low = msg.lower()
    if 'rate limit' in low or '429' in msg:
        return ("😴 WildNest AI is taking a short breather — it's hit today's free "
                "usage limit. Please try again in a little while (the limit resets "
                "daily).")
    if '401' in msg or 'invalid api key' in low or 'authentication' in low:
        return ("⚠️ WildNest couldn't authenticate with Groq. Please check that "
                "your GROQ_API_KEY in .env is a valid key from console.groq.com.")
    return f"⚠️ WildNest hit an error talking to the AI: {msg}"


def _chat_completion(model, messages):
    client = _get_client()
    kwargs = {'model': model, 'messages': messages}
    # VISION_MODEL is a reasoning model that emits chain-of-thought before the
    # real answer — reasoning_format='hidden' tells Groq to strip it server-side
    # so caretakers never see the model's scratchwork. TEXT_MODEL isn't a
    # reasoning model and rejects this param outright (400 error), so it's only
    # sent for VISION_MODEL.
    if model == VISION_MODEL:
        kwargs['reasoning_format'] = 'hidden'
    resp = client.chat.completions.create(**kwargs)
    text = resp.choices[0].message.content
    # backup in case a future model ignores the flag or uses <think> unprompted
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return text.strip()


# ---- chat --------------------------------------------------------------------

def get_chat_reply(animal, history, user_message, image_path=None):
    """history: list of {'role': 'user'|'assistant', 'content': str} (chronological).
    image_path: optional absolute path to a photo the caretaker just uploaded —
    when present, the model is asked to look for signs of injury/illness/abnormal
    behaviour in the photo, in light of this animal's known baseline.
    Returns the assistant's reply text (or a friendly fallback message)."""
    if not is_configured():
        return ("⚙️ WildNest AI isn't connected yet. Add your free Groq API key "
                "to the .env file (GROQ_API_KEY=...) and restart the app "
                "to start chatting about this pet.")

    system_instruction = build_system_context(animal, query=user_message)
    messages = [{'role': 'system', 'content': system_instruction}]
    for m in history:
        messages.append({'role': m['role'], 'content': m['content']})

    model = TEXT_MODEL
    if image_path:
        try:
            with open(image_path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
            ext = os.path.splitext(image_path)[1].lstrip('.').lower() or 'jpeg'
            if ext == 'jpg':
                ext = 'jpeg'
            messages.append({
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': (
                        f"The caretaker uploaded a photo of {animal.name} along with this message: "
                        f"\"{user_message}\"\n\nCarefully look at the photo for any visible signs of "
                        f"injury, illness, abnormal posture, skin/coat/scale condition, or distress — "
                        f"comparing against {animal.name}'s known baseline and stress triggers above. "
                        f"Clearly state whether anything looks concerning, and what the caretaker should "
                        f"do next (including when to contact a vet).")},
                    {'type': 'image_url', 'image_url': {'url': f'data:image/{ext};base64,{b64}'}},
                ],
            })
            model = VISION_MODEL
        except Exception:
            messages.append({'role': 'user', 'content': user_message})
    else:
        messages.append({'role': 'user', 'content': user_message})

    try:
        return _chat_completion(model, messages)
    except Exception as e:  # noqa: BLE001
        return _friendly_error(e)


def generate_todays_meal_plan(animal, weather):
    """Generate breakfast/lunch/dinner + care suggestions for TODAY, factoring in
    real current weather (temp/humidity) at the pet's location plus its own history.
    weather: dict from weather.get_current_weather(), or None if unavailable."""
    if not is_configured():
        return "⚙️ WildNest AI isn't connected yet. Add your GROQ_API_KEY to .env and restart."

    system_instruction = build_system_context(
        animal, query='daily meal plan, feeding amounts, diet, temperature and humidity care')

    if weather:
        weather_block = (
            f"VERIFIED CURRENT WEATHER (from a live weather API — treat these as exact, "
            f"authoritative facts, do not estimate or override them):\n"
            f"Location: {weather['place_name']}\n"
            f"Local observation time: {weather['observed_at']} ({weather['timezone']})\n"
            f"Temperature: {weather['temp_f']}°F ({weather['temp_c']}°C)\n"
            f"Humidity: {weather['humidity_pct']}%\n"
            f"Conditions: {weather['description']}"
        )
    else:
        weather_block = ("Current weather is unavailable (no Current Location set for this pet, "
                         "or the lookup failed) — base suggestions on the pet's history only, "
                         "and do not invent or guess a temperature/humidity.")

    prompt = f"""{weather_block}

Generate TODAY's plan for {animal.name} based on the weather data above and everything
you know about {animal.name} above. Respond in this exact structure using short markdown:

## 🍳 Breakfast
One short suggestion (what/how much), then *in italics* a one-line reason tied to
today's weather and/or {animal.name}'s history.

## 🍽️ Lunch
Same format.

## 🌙 Dinner
Same format.

## 💧 Today's Care Tips
2-3 short bullet points (e.g. hydration frequency, shade/cooling or warming, activity
level, misting/showering if relevant to the species) — each with a brief *reason in
italics* that names the actual temperature and/or humidity number given above.

Keep it tight — this is a quick daily glance, not an essay. When you reference the
weather, quote the exact numbers given above (e.g. "87°F", "78% humidity") — never
approximate, round significantly, or make up different numbers."""

    messages = [
        {'role': 'system', 'content': system_instruction},
        {'role': 'user', 'content': prompt},
    ]
    try:
        return _chat_completion(TEXT_MODEL, messages)
    except Exception as e:  # noqa: BLE001
        return _friendly_error(e)


# ---- pet matching ----------------------------------------------------------

def _pet_catalog_line(p):
    """Compact one-line summary of a pet for the matching prompt."""
    logs = list(p.env_logs)
    temps = [l.temperature_f for l in logs if l.temperature_f is not None]
    hums = [l.humidity_pct for l in logs if l.humidity_pct is not None]
    weights = [l.weight_g for l in logs if l.weight_g is not None]
    avg_temp = round(statistics.mean(temps), 1) if temps else None
    avg_hum = round(statistics.mean(hums), 1) if hums else None
    medical = '; '.join(r.title for r in list(p.medical_records)[:3]) or 'none'
    return (
        f"ID {p.id}: {p.name}, species {p.species}"
        f"{(' (' + p.common_name + ')') if p.common_name else ''}, "
        f"age {p.age_years if p.age_years is not None else 'unknown'}, "
        f"origin {p.origin}, location {p.current_location or 'unspecified'}. "
        f"Stress triggers: {p.stress_triggers or 'none noted'}. "
        f"Diet: {p.dietary_requirements or 'unspecified'}. "
        f"Baseline temp {avg_temp if avg_temp is not None else '?'}F, "
        f"humidity {avg_hum if avg_hum is not None else '?'}%. "
        f"Current weight {(str(int(weights[-1])) + 'g') if weights else 'unknown'}. "
        f"Medical history: {medical}."
    )


def _extract_json_array(text):
    """Pull the first JSON array out of a model response (tolerates markdown fences)."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?', '', text).strip()
    text = re.sub(r'```$', '', text).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r'\[.*\]', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


def match_pets(requirements_text, pets):
    """Score every pet against the adopter's requirements in ONE call.
    Returns a list of {animal, score, reason} sorted by score desc, or None on failure."""
    if not pets:
        return []
    if not is_configured():
        return None

    catalog = '\n'.join(_pet_catalog_line(p) for p in pets)
    prompt = f"""You are matching an adopter with rescued/exotic pets available for rehoming.

=== ADOPTER'S REQUIREMENTS ===
{requirements_text}

=== AVAILABLE PETS ===
{catalog}

For EACH pet, rate from 0 to 100 how well it fits this adopter, weighing:
- species preference, care difficulty vs the adopter's experience,
- climate/enclosure needs (temperature, humidity) vs what they can provide,
- daily time commitment, space, and any health considerations,
- location proximity if relevant.

Respond with ONLY a JSON array (no markdown, no extra text), one object per pet:
[{{"id": <pet id>, "score": <0-100 integer>, "reason": "<one short sentence why>"}}]"""

    by_id = {p.id: p for p in pets}

    try:
        raw = _chat_completion(TEXT_MODEL, [{'role': 'user', 'content': prompt}])
        data = _extract_json_array(raw)
        if data is None:
            return None
        results = []
        for item in data:
            pid = item.get('id')
            if pid in by_id:
                try:
                    score = max(0, min(100, int(item.get('score', 0))))
                except (ValueError, TypeError):
                    score = 0
                results.append({
                    'animal': by_id[pid],
                    'score': score,
                    'reason': str(item.get('reason', '')).strip(),
                })
        # include any pets the model skipped, at the bottom
        scored_ids = {r['animal'].id for r in results}
        for p in pets:
            if p.id not in scored_ids:
                results.append({'animal': p, 'score': 0, 'reason': 'Not enough data to score.'})
        results.sort(key=lambda x: x['score'], reverse=True)
        return results
    except Exception:  # noqa: BLE001
        return None


# ---- transition-day notifications ("from the pet") ------------------------

def _ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f'{n}{suffix}'


def _parse_title_body(text, fallback_title):
    """Pull TITLE:/BODY: lines out of the model response; tolerant of formatting slips."""
    title_match = re.search(r'TITLE:\s*(.+)', text)
    body_match = re.search(r'BODY:\s*(.+)', text, re.DOTALL)
    if title_match and body_match:
        title = title_match.group(1).strip().strip('"')
        body = body_match.group(1).strip()
        return title, body
    # fallback: first non-empty line is the title, rest is the body
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    if not lines:
        return fallback_title, "I'm settling in — check on me when you can!"
    return lines[0].strip('"'), ' '.join(lines[1:]) or "Just checking in today."


def generate_transition_notification(animal, day_number):
    """Write a short, first-person 'update from the pet' comparing its life before
    and after this handover, with one concrete suggestion. Returns (title, body)."""
    fallback_title = f"It's my {_ordinal(day_number)} day with you"
    if not is_configured():
        return None

    logs = list(animal.env_logs)
    handover = animal.handover_date
    before = [l for l in logs if handover and l.timestamp < handover]
    after = [l for l in logs if not handover or l.timestamp >= handover]

    before_summary = build_analytics_summary(before)
    after_summary = build_analytics_summary(after)

    prompt = f"""You are {animal.name}, a {animal.species}, writing a short first-person
daily note to your NEW caretaker, who took you in {day_number} day(s) ago. Use the data
below to ground it in reality — comparing your life before this move to how you're doing
now, if there's a notable difference worth mentioning. Speak as the animal — simple,
warm, a little vulnerable, never melodramatic. Never invent facts not supported by the
data below (species-appropriate food/play ideas from general knowledge are fine).

=== MY LIFE BEFORE (previous home/carer) ===
{before_summary}

=== MY LIFE SINCE THE MOVE ({day_number} day(s) with you) ===
{after_summary}

=== MY KNOWN TRIGGERS & NEEDS ===
Stress triggers: {_fmt(animal.stress_triggers)}
Diet: {_fmt(animal.dietary_requirements)}

Respond in EXACTLY this format, nothing else:
TITLE: It's my {_ordinal(day_number)} day with you — <5-8 word warm continuation, e.g. "and I miss my old sunbathing spot">
BODY: <one short, warm paragraph (3-4 sentences) in first person as {animal.name}, covering
ALL of: (1) how I'm feeling today, tied to a real observation from the data if there is
one, (2) what I'd like to do today, (3) what I'd like to eat today, (4) one simple way
you could play with me today. Keep the whole thing brief and easy to read in one glance —
no headers, no bullet points, just a natural flowing note.>"""

    try:
        raw = _chat_completion(TEXT_MODEL, [{'role': 'user', 'content': prompt}])
    except Exception as e:  # noqa: BLE001
        raw = _friendly_error(e)

    # any of these prefixes means the call returned a fallback message, not a real reply
    if not raw or raw[0] in ('⚙', '⚠', '😴'):
        return None
    return _parse_title_body(raw, fallback_title)
