"""WildNest AI — per-pet chat assistant powered by Google Gemini.

The model is given the specific animal's full profile + a summary of its
environmental analytics as context, so answers are personalised to THAT animal.
It also draws on Gemini's general knowledge of animal care.
"""
import os
import statistics

# tried in order with a real test call; the first one that actually
# responds (not just "listed") is cached and reused.
CANDIDATE_MODELS = [
    'gemini-2.0-flash',
    'gemini-2.0-flash-001',
    'gemini-flash-latest',
    'gemini-1.5-flash',
    'gemini-1.5-flash-latest',
    'gemini-1.5-flash-002',
    'gemini-1.5-pro',
    'gemini-2.5-flash',
    'gemini-pro',
]

# ---- lazy Gemini client ----------------------------------------------------

_configured = False
_resolved_model = None


def _get_api_key():
    return os.getenv('GEMINI_API_KEY', '').strip()


def is_configured():
    key = _get_api_key()
    return bool(key) and key != 'PASTE_YOUR_NEW_KEY_HERE'


def _ensure_configured():
    global _configured
    if _configured:
        return True
    if not is_configured():
        return False
    import google.generativeai as genai
    genai.configure(api_key=_get_api_key())
    _configured = True
    return True


def _model_actually_works(genai, name):
    """Make a tiny real call — 'listed' isn't the same as 'callable' on this key."""
    try:
        test = genai.GenerativeModel(name)
        test.generate_content('hi', generation_config={'max_output_tokens': 5})
        return True
    except Exception:
        return False


def _resolve_model_name(exclude=None):
    """Find a Gemini model this specific API key can actually call, and cache it."""
    global _resolved_model
    if _resolved_model and _resolved_model != exclude:
        return _resolved_model
    import google.generativeai as genai
    for name in CANDIDATE_MODELS:
        if name == exclude:
            continue
        if _model_actually_works(genai, name):
            _resolved_model = name
            return _resolved_model
    # nothing worked — fall back to the first candidate so the error message is informative
    _resolved_model = CANDIDATE_MODELS[0]
    return _resolved_model


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


def build_system_context(animal):
    """Full personalised instruction for the model about this specific animal."""
    a = animal
    analytics = build_analytics_summary(list(a.env_logs))
    medical = build_medical_summary(list(a.medical_records))
    return f"""You are WildNest, a warm, knowledgeable assistant that helps caretakers
look after their specific rescued or exotic pet. You are speaking with the
current caretaker of the pet described below. Use BOTH this pet's own
records AND your general knowledge of animal husbandry, species behaviour, diet,
enclosure needs, and health to give personalised, practical, caring guidance.
Refer to it as "your pet" or by its name — never call it "the animal".

=== THIS PET'S PROFILE ===
Name: {a.name}
Species: {a.species}{(' (' + a.common_name + ')') if a.common_name else ''}
Age: {_fmt(a.age_years, ' years')}
Sex: {_fmt(a.sex)}
Origin: {a.origin}
Known stress triggers: {_fmt(a.stress_triggers)}
Dietary requirements: {_fmt(a.dietary_requirements)}
Background: {_fmt(a.rescue_reason)}

=== THIS PET'S MEDICAL HISTORY (most recent first) ===
{medical}

=== THIS PET'S LOGGED ANALYTICS ===
{analytics}

=== HOW TO RESPOND ===
- Always tailor advice to THIS pet ({a.name}, a {a.species}) using its records above.
- Refer to its actual data when relevant (e.g. its weight trend, stress pattern, triggers).
- Be concise, friendly, and practical. Use short paragraphs or bullet points.
- If something suggests a possible health emergency, clearly advise contacting a
  veterinarian — you assist, you do not replace professional veterinary care.
- If data is missing, say so and suggest what the caretaker could start logging."""


# ---- chat ------------------------------------------------------------------

def get_chat_reply(animal, history, user_message, image_path=None):
    """history: list of {'role': 'user'|'assistant', 'content': str} (chronological).
    image_path: optional absolute path to a photo the caretaker just uploaded —
    when present, the model is asked to look for signs of injury/illness/abnormal
    behaviour in the photo, in light of this animal's known baseline.
    Returns the assistant's reply text (or a friendly fallback message)."""
    if not is_configured():
        return ("⚙️ WildNest AI isn't connected yet. Add your free Google Gemini "
                "API key to the .env file (GEMINI_API_KEY=...) and restart the app "
                "to start chatting about this pet.")

    if not _ensure_configured():
        return "⚙️ WildNest AI isn't configured. Please check your API key."

    system_instruction = build_system_context(animal)
    gemini_history = [
        {'role': 'model' if m['role'] == 'assistant' else 'user',
         'parts': [m['content']]}
        for m in history
    ]

    # build the message to send: text, or text + photo for visual health/behaviour analysis
    message_parts = [user_message]
    if image_path:
        try:
            from PIL import Image
            message_parts = [
                f"The caretaker uploaded a photo of {animal.name} along with this message: "
                f"\"{user_message}\"\n\nCarefully look at the photo for any visible signs of "
                f"injury, illness, abnormal posture, skin/coat/scale condition, or distress — "
                f"comparing against {animal.name}'s known baseline and stress triggers above. "
                f"Clearly state whether anything looks concerning, and what the caretaker should "
                f"do next (including when to contact a vet).",
                Image.open(image_path),
            ]
        except Exception:
            message_parts = [user_message]  # fall back to text-only if the image can't be read

    def _call(model):
        chat = model.start_chat(history=gemini_history)
        return chat.send_message(message_parts).text.strip()

    return _run_with_retry(system_instruction, _call)


def _run_with_retry(system_instruction, call_fn):
    """Shared retry/error-handling wrapper: tries the cached model, re-resolves once
    if it's gone stale, and turns exceptions into friendly WildNest-branded messages."""
    global _resolved_model
    import google.generativeai as genai

    failed_name = None
    for attempt in range(2):
        model_name = _resolve_model_name(exclude=failed_name)
        try:
            model = genai.GenerativeModel(model_name, system_instruction=system_instruction)
            return call_fn(model)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            is_model_issue = '404' in msg or 'not found' in msg.lower() or 'no longer available' in msg.lower()
            if is_model_issue and attempt == 0:
                failed_name = model_name
                _resolved_model = None  # force re-resolution on the next loop
                continue
            if 'API_KEY' in msg or 'api key' in msg.lower() or 'PERMISSION' in msg.upper():
                return ("⚠️ WildNest couldn't authenticate with Gemini. Please check that "
                        "your GEMINI_API_KEY in .env is a valid key from aistudio.google.com.")
            return f"⚠️ WildNest hit an error talking to the AI: {msg}"


def generate_todays_meal_plan(animal, weather):
    """Generate breakfast/lunch/dinner + care suggestions for TODAY, factoring in
    real current weather (temp/humidity) at the pet's location plus its own history.
    weather: dict from weather.get_current_weather(), or None if unavailable."""
    if not is_configured():
        return "⚙️ WildNest AI isn't connected yet. Add your GEMINI_API_KEY to .env and restart."
    if not _ensure_configured():
        return "⚙️ WildNest AI isn't configured. Please check your API key."

    system_instruction = build_system_context(animal)

    if weather:
        weather_block = (
            f"Current weather at {weather['place_name']}: {weather['temp_f']}°F "
            f"({weather['temp_c']}°C), {weather['humidity_pct']}% humidity, {weather['description']}."
        )
    else:
        weather_block = ("Current weather is unavailable (no location set for this pet, or "
                         "lookup failed) — base suggestions on the pet's history only.")

    prompt = f"""{weather_block}

Generate TODAY's plan for {animal.name} based on this weather and everything you know
about {animal.name} above. Respond in this exact structure using short markdown:

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
italics* tied to today's actual temperature/humidity.

Keep it tight — this is a quick daily glance, not an essay. Always tie suggestions to
the specific weather numbers and this pet's own data, not generic advice."""

    def _call(model):
        return model.generate_content(prompt).text.strip()

    return _run_with_retry(system_instruction, _call)
