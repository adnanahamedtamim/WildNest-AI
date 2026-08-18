"""WildNest AI — per-pet chat assistant powered by Together AI.

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

import rag

TEXT_MODEL = 'meta-llama/Meta-Llama-3-8B-Instruct-Turbo'
VISION_MODEL = 'meta-llama/Meta-Llama-3-8B-Instruct-Turbo'

# ---- lazy Together AI client -------------------------------------------------------

_client = None


def _get_api_key():
    return os.getenv('TOGETHER_API_KEY', '').strip()


def is_configured():
    key = _get_api_key()
    return bool(key) and key != 'PASTE_YOUR_NEW_KEY_HERE'


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(
            api_key=_get_api_key(),
            base_url="https://api.together.xyz/v1"
        )
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
    for r in records[:8]:
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

    return f"""You are WildNest, a warm, knowledgeable assistant that helps caretakers provide expert animal care.

=== ANIMAL PROFILE ===
Species: {a.species}
Name: {a.name}
Age: {_fmt(a.age_years, ' years')}
Weight: {_fmt(a.weight_g, 'g')}
Health status: {a.health_status or 'not specified'}
{handover_line}

=== MEDICAL HISTORY ===
{medical}

=== ENVIRONMENTAL ANALYTICS ===
{analytics}

{meal_plan_block}

{rag_block}

=== YOUR ROLE ===
1. **Answer grounded in this animal's data first.** Always use this animal's logged records (medical
   history, weight trends, environmental logs, caretaker notes) as the primary foundation for advice.
2. **Draw on general knowledge second.** Only supplement with general animal-care knowledge when
   the specific data doesn't directly answer the question.
3. **Cite your sources.** When referencing supplementary species information, cite the source in square
   brackets [like this]. Never make up citations.
4. **Be warm but precise.** This is a caretaker who trusts you with a living animal — be empathetic
   and encouraging, but never guess or hedge critical medical advice. If uncertain, say so.
5. **Respect the meal plan.** If a meal plan has already been generated today, refer back to it rather
   than contradicting or repeating it.

Answer the caretaker's question in 2–3 sentences, then elaborate if needed."""


def get_chat_reply(animal, history, user_message, image_path=None):
    """Get a personalised AI reply for this specific animal, optionally analysing a photo."""
    if not is_configured():
        return "❌ AI is not configured. Set TOGETHER_API_KEY in .env."

    system_prompt = build_system_context(animal, user_message)

    messages = [{'role': m['role'], 'content': m['content']} for m in history]

    if image_path:
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        messages.append({
            'role': 'user',
            'content': [
                {'type': 'text', 'text': user_message},
                {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{image_data}'}}
            ]
        })
    else:
        messages.append({'role': 'user', 'content': user_message})

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=VISION_MODEL if image_path else TEXT_MODEL,
            messages=[{'role': 'system', 'content': system_prompt}] + messages,
            max_tokens=1024,
            temperature=0.7
        )
        reply = response.choices[0].message.content
        reply = re.sub(r'<think>.*?</think>', '', reply, flags=re.DOTALL)
        return reply
    except Exception as e:
        return f"⚠️ WildNest hit an error talking to the AI: {e}"


def generate_todays_meal_plan(animal, weather=None):
    """Generate a species-appropriate meal plan for today based on weather."""
    if not is_configured():
        return None

    try:
        if weather and weather.get('temperature') is not None:
            temp = weather['temperature']
            humidity = weather.get('humidity', 50)
        else:
            import requests
            resp = requests.get(
                'https://api.open-meteo.com/v1/forecast',
                params={
                    'latitude': animal.location_latitude or 40.7128,
                    'longitude': animal.location_longitude or -74.0060,
                    'current': 'temperature_2m,relative_humidity_2m'
                },
                timeout=5
            ).json()
            temp = resp['current']['temperature_2m']
            humidity = resp['current']['relative_humidity_2m']
    except Exception:
        temp, humidity = 72, 50

    client = _get_client()
    system = f"""You are a wildlife nutritionist. Generate a detailed, species-specific meal plan.
Animal: {animal.species}, {_fmt(animal.age_years, ' years old')}, {_fmt(animal.weight_g, 'g')}
Current weather: {temp}°F, {humidity}% humidity
Include: portions, feeding times, hydration (adjust for heat/humidity), treat options.
Format as a readable daily schedule."""

    try:
        response = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': f'Generate today\'s meal plan for {animal.name} ({animal.species}).'}
            ],
            max_tokens=1024,
            temperature=0.7
        )
        plan = response.choices[0].message.content
        return plan, None
    except Exception as e:
        return None, f"⚠️ Meal plan generation failed: {e}"


def match_pets(adopters):
    """Score and rank adopters for each animal in the shelter based on compatibility."""
    if not is_configured():
        return {}, "❌ AI is not configured. Set TOGETHER_API_KEY in .env."

    try:
        from models import Animal
        animals = Animal.query.all()
        matches = {}

        for animal in animals:
            context = f"""Animal: {animal.name} ({animal.species}), age {_fmt(animal.age_years, ' years')},
health status: {animal.health_status or 'good'}, medical history: {build_medical_summary(list(animal.medical_records))}"""

            client = _get_client()
            response = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {'role': 'system', 'content': 'You are an animal adoption specialist. Score adopter compatibility (0-100) for this animal.'},
                    {'role': 'user', 'content': f'{context}\n\nAdopters: {json.dumps(adopters)}\n\nRank by compatibility score.'}
                ],
                max_tokens=512,
                temperature=0.7
            )
            matches[animal.id] = response.choices[0].message.content

        return matches, None
    except Exception as e:
        return {}, f"⚠️ Matching failed: {e}"


def generate_transition_notification(animal, day_number):
    """Generate a care milestone notification (e.g., 'Day 3 with {animal.name}')."""
    if not is_configured():
        return None

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[
                {'role': 'system', 'content': 'You are a wildlife care coordinator. Generate a brief, warm milestone message (under 100 chars).'},
                {'role': 'user', 'content': f'Animal: {animal.name} ({animal.species}). Day {day_number} milestone. Generate a short, encouraging title and body (2 sentences).'}
            ],
            max_tokens=200,
            temperature=0.8
        )
        text = response.choices[0].message.content
        lines = text.split('\n', 1)
        title = lines[0][:80]
        body = lines[1] if len(lines) > 1 else ''
        return (title, body)
    except Exception:
        return None
