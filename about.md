# 🐾 WildNest — Where Rescue Meets Rehome, Powered by AI

## Inspiration

Every year, an estimated **five million exotic and wild animals** pass through rescue centers, wildlife rehabilitation facilities, and informal shelters around the world. They arrive traumatized, malnourished, and often with no history — no medical records, no behavioral notes, no way to tell the next caretaker what triggers their stress or what food they will actually eat.

The stories we heard while researching this problem broke us in the same way, over and over:

- A sulcata tortoise re-homed three times in two years because no adopter was told he needed **80°F basking spots year-round**. Each new owner learned only after the animal fell ill.
- A ball python surrendered because the rescuer's paper logbook was lost in a flood. The vet had to guess dosages from scratch.
- An adopter matched with a bearded dragon he was completely unequipped for, because "matching" meant filling out a paper form and hoping someone read it.

The domestic pet world has solved most of this. **Petfinder, Rover, Chewy**, and dozens of vet apps mean a dog or cat is rarely lost in the system. But exotic animals — reptiles, birds, tortoises, small mammals — have been left behind by every one of them.

**WildNest** is our answer. It is the first end-to-end platform that tracks a rescued exotic animal from the moment it enters care, through every meal, log, and health scan, all the way to a permanent home — with a compatible adopter matched by AI, a formal handover certificate, and daily transition support during the first month in the new home.

We wanted to build the thing we wished every shelter volunteer, wildlife rehabilitator, and first-time exotic owner already had.

---

## What it does

WildNest is a full-stack Flask application organized around a single principle: **every rescued animal has a lifecycle, and every stage of that lifecycle should be captured, analyzed, and shared**.

### 1. Rescue Intake & Animal Profiles
Staff create a rich profile the moment an animal arrives — species, age, sex, rescue circumstances, medical history, stress triggers, dietary requirements, and photos. Each animal gets a stable identity from day one.

### 2. Environmental Logging & Live Health Dashboards
Caretakers log daily observations — temperature, humidity, lighting hours, feeding amount, weight, stress level, activity level, behavioral notes, even short videos of unusual behavior. Every log flows into **interactive Plotly charts** that visualize trends over time, so a slow decline in weight or a spike in stress becomes visible immediately instead of buried in a spreadsheet.

### 3. WildSight AI — Photo-Based Health Analysis
Staff or adopters snap a photo of the animal. **Google Gemini's vision model** analyzes the image and returns a structured health assessment: visible signs of stress or illness, weight condition, coat/scale quality, and a **severity tier** (`normal → watch → contact_staff → emergency`) that maps directly to the notification bell. Critical findings turn the bell red.

### 4. AI Chat, Grounded in the Animal's Own Data
Every animal has a dedicated chat. Ask a question about a specific pet and the AI answers using:
- The animal's **own logged history** (temperature averages, feeding patterns, weight trend, stress spikes) — the primary and always-trusted source
- A **RAG knowledge base** we built from species-specific care references, indexed with **sentence-transformers embeddings** and retrieved via **ChromaDB** vector search — used as secondary grounding with visible source citations

The result is a chat that never hallucinates dosage advice and never confuses one animal for another.

### 5. Weather-Aware Meal Plans
A reptile's metabolism is temperature-dependent. A parrot's water intake changes with humidity. WildNest pulls **live weather data** for the animal's location and factors it into a daily meal plan generated on demand — portion sizes, feeding frequency, and hydration all adjust to real-world conditions.

### 6. QR Passport
Every animal receives a **QR-code passport** backed by an unguessable token. Scan it and any vet, shelter, or new owner gets instant access to the animal's identity, medical history, and care requirements. No app install. No login. Just a public link that works from any phone camera.

### 7. Rehoming Feed + AI-Powered Matching
When an animal is ready, staff list it on the rehoming feed. Adopters can browse manually — or use **AI matching**. They describe their experience level, living space, climate, time availability, and location. The AI ranks every listed animal by compatibility with a written explanation for each match. The `owner_id != current_user.id` filter guarantees adopters never match their own listings.

### 8. Formal Handover + 30-Day Transition Notifications
A confirmed adoption creates a **cryptographic handover certificate** with a unique 8-character ID transferring ownership. For **30 days after adoption**, the new owner receives daily AI-generated notifications written **from the pet's perspective** — helping them understand what their new companion is feeling as it adjusts. Vaccination due-dates auto-generate alerts on the same channel.

### 9. Privacy, Ownership & Handover Control
The original rescuer keeps read access to animals they saved, unless the new owner explicitly toggles `profile_private`. Former rescuers can also hide handed-over animals from their own dashboard without affecting the current owner. Every relationship is modeled at the database level.

---

## How we built it

### Architecture

WildNest is a **Flask 3** monolith deliberately kept simple enough to reason about end-to-end, but structured with clear module boundaries.

| Layer | Technology |
|---|---|
| Web framework | Flask + Flask-Login |
| ORM & migrations | Flask-SQLAlchemy with a lightweight `ensure_schema()` runner |
| Database | SQLite for dev, **PostgreSQL** for production (auto-detected via `DATABASE_URL`) |
| AI — chat & vision | **Google Gemini** (`gemini-2.0-flash`) |
| RAG — retrieval | **ChromaDB** persistent client + **sentence-transformers** (`all-MiniLM-L6-v2`) |
| Charts | **Plotly.js** rendered server-side |
| Weather | Open-Meteo API |
| QR generation | `qrcode` Python library |
| Production server | Gunicorn behind Render's reverse proxy |
| Frontend | Server-rendered Jinja2 + progressive-enhancement vanilla JS + custom CSS design system |

### Data model — 10 interlinked entities

```
User ─┬─ owns → Animal ─┬─ EnvironmentalLog
      │                 ├─ DailyMetric
      │                 ├─ MedicalRecord (with vaccination auto-detection)
      │                 ├─ WildSightAnalysis (photo scans)
      │                 ├─ ChatMessage (AI conversations)
      │                 ├─ RehomeListing → AdoptionRequest
      │                 └─ HandoverRecord (with certificate_id)
      └─ receives → Notification (transition + vaccination alerts)
```

Every relationship has explicit foreign keys, cascade rules, and — as of the latest release — **database-level CHECK constraints** enforcing valid ranges on every measured field.

### The RAG pipeline

$$
\text{answer} = \text{Gemini}\left(\text{prompt} \oplus \underbrace{\text{profile} \oplus \text{logs}}_{\text{primary context}} \oplus \underbrace{\text{top-}k \text{ retrieved chunks}}_{\text{secondary grounding}}\right)
$$

The chunks are retrieved by ranking every indexed care-reference paragraph against the user's query embedding using cosine similarity:

$$
\text{score}(q, c) = \frac{\vec{q} \cdot \vec{c}}{\|\vec{q}\|\,\|\vec{c}\|}
$$

where $\vec{q}$ is the query embedding and $\vec{c}$ is the chunk embedding, both produced by `all-MiniLM-L6-v2`. We take the top $k=3$ chunks and cite the source file in the UI, so the user can verify the AI's grounding.

Crucially, the RAG layer is **strictly secondary**. If retrieval fails, the chat still works using only the animal's own data — because a chat that hallucinates about your specific pet is worse than a chat that admits it has no reference material.

### The AI matching score

For adoption matching, we send the adopter's requirements and every available listing into Gemini with a structured prompt that returns a compatibility score $s \in [0, 100]$ per animal, plus a written rationale. Under the hood the prompt asks the model to weight:

$$
s = 0.35 \cdot \text{experience-fit} + 0.25 \cdot \text{space-fit} + 0.20 \cdot \text{climate-fit} + 0.20 \cdot \text{time-fit}
$$

The weights are baked into the system prompt, not hard-coded in Python — which lets us tune matching behavior without a redeploy.

### Performance & reliability engineering

We did not just build features. We hardened the app for production:

- **N+1 query elimination**: the dashboard originally ran $1 + 3N$ queries for $N$ animals. Rewritten with `selectinload` and batched `IN` queries, it now runs a constant $\sim 4$ queries regardless of animal count.
- **Transaction safety**: every write path (registration, handover, listing creation) is wrapped in try/except with `db.session.rollback()`, and a global `SQLAlchemyError` handler catches anything that slips through.
- **Race conditions**: two simultaneous signups with the same email used to both pass the existence check and one would crash. Now the `IntegrityError` on the unique constraint is caught and rendered as a friendly message.
- **Connection pooling**: PostgreSQL connections use `pool_pre_ping=True` and `pool_recycle=280` so we never hand out a connection that Render's managed Postgres has silently dropped.
- **Database CHECK constraints** on `age_years`, humidity ranges, stress/activity levels, feeding amounts, and enum fields — so even a bad direct SQL insert cannot corrupt the data.
- **Background RAG warmup**: the embedding model + vector index take ~30s to load on first use. We eagerly warm both in a daemon thread at app startup, so no user ever pays that cost.
- **`ProxyFix` middleware**: `url_for(_external=True)` — used by the QR passport — now correctly generates HTTPS URLs with the real public host behind Render's reverse proxy.

---

## Challenges we ran into

### 1. The RAG-warmup bug that only appeared in production
Our first RAG implementation "worked" locally. The vector store loaded, the collection was indexed, everything looked fine. But the very first real user query still hung for 30 seconds. It turned out our warmup only touched the *collection* — not the embedder. The collection warmed up in ~2s while the SentenceTransformer model stayed cold until it was needed to encode the actual query. The fix was one line: eagerly call `_get_embedder()` alongside `_get_collection()`. But finding it required us to timestamp every step of the first-request path.

### 2. The invisible chart on mobile
Our Plotly charts rendered perfectly on desktop and mysteriously became a **razor-thin distorted band** on real mobile devices — but not in DevTools mobile emulation. We chased it for hours. The root cause was a **race between CSS load and Plotly's initial measurement**: on slow mobile networks, Plotly measured the container width before the CSS defining that container had finished loading, so it computed a width of a few pixels and rendered accordingly. The fix was a `window.addEventListener('load', ...)` that forces `Plotly.Plots.resize()` on every chart after all resources are in — a small line of code that took an evening to justify.

### 3. The split-layout that overlapped on mobile
Our login and register pages used a 50/50 flex split between the brand panel and the form. On a 375px-wide phone, the form needed 413px of vertical space in 398px of available space — so the two sections visibly overlapped. We spent an hour blaming a `-42px` margin on a decorative cat illustration before realizing the real problem: the flex split was measuring by *proportion* when it needed to measure by *content*. The fix was changing the brand panel to `flex: 0 0 auto` (shrink to content) and the form panel to `flex: 1 1 auto` (take the rest) — plus hiding the decorative art below 768px.

### 4. The registration race condition
Two people (or one person with two tabs, or one impatient double-click) could hit `/register` with the same email at the same time. Both requests would pass the "does this email exist?" check, both would insert, and the second would crash with an unhandled `IntegrityError` on the unique constraint. We now catch the error, roll back the session, and render the same friendly "email already exists" message. Verified by firing two concurrent `curl` requests and confirming exactly one succeeded.

### 5. The Render out-of-memory crash
Free-tier Render instances have **512 MB of RAM**. Our production build loaded PyTorch + `sentence-transformers` (~400 MB) plus ChromaDB (~100 MB) plus the Flask app itself, and the instance was OOM-killed on startup. We wrote a lightweight fallback that swaps `sentence-transformers` for Gemini's embedding API and ChromaDB for a JSON cache with pure-Python cosine similarity — same semantic retrieval, ~350 MB less memory. The full-fat stack still runs in production on paid tiers; the fallback is one branch flip away.

### 6. Postgres URI schema changes
Render (and Heroku before it) still hand out the legacy `postgres://` URI scheme, which **SQLAlchemy 1.4+ rejects**. We rewrite it to `postgresql://` before it ever touches the engine — a two-line fix that would otherwise have crashed the app at startup with a cryptic dialect error.

### 7. The transition-notification dedupe race
Two overlapping requests could each generate the same day-N transition note for the same pet, so users would see duplicates in their notification bell. We solved it with a **partial unique index** — `UNIQUE(user_id, animal_id, day_number) WHERE category = 'transition'` — that lets the database itself enforce "at most one transition note per pet per day, no matter how many requests race." Vaccination notifications reuse `day_number=0` for distinct alerts over time, so they're deliberately excluded from the constraint.

---

## What we learned

### Engineering lessons
- **AI grounding is the whole game.** A chat that hallucinates dosages for a specific animal is dangerous. We learned to structure prompts so the AI's "sources of truth" are unambiguous and layered: profile > logs > RAG > general knowledge.
- **The database is the last line of defense.** Application-level validation catches most bad data. `CHECK` constraints, unique indexes, and foreign keys catch the rest — including the writes you didn't know were happening.
- **Race conditions hide until you look for them.** Every check-then-insert pattern is a bug in disguise. We now assume every write path has a concurrent twin.
- **Warmup where the user isn't.** Any expensive first-call cost belongs in a background thread at startup, not on the shoulders of whoever happens to visit first.
- **Free-tier constraints teach discipline.** Being OOM-killed on Render's 512MB free tier forced us to actually measure our dependencies — and to design a lightweight fallback we would never have written otherwise.

### Product lessons
- **Exotic pet care is a knowledge asymmetry problem.** Adopters don't know what they don't know. The RAG citations exist so an adopter can read the source that told the AI *"a bearded dragon needs UVB every day"* — and start learning.
- **The rescuer's perspective matters as much as the adopter's.** A rehoming platform that erases the rescuer's history the moment ownership transfers loses the most important context. We kept the rescuer as a first-class relationship in the data model.
- **Notifications should feel personal.** AI-written "from the pet's perspective" transition notes are gimmicky in isolation. They become powerful when they arrive one per day for 30 days after a difficult adoption — the exact window when new owners are most likely to give up.

### Design lessons
- **Full-viewport split layouts on mobile need `flex: 0 0 auto`.** Anything else overlaps. We now know this in our bones.
- **Test on real devices, not just emulators.** The Plotly chart bug and the login overlap were both invisible in DevTools.

---

## Built With

`python` · `flask` · `flask-sqlalchemy` · `flask-login` · `postgresql` · `sqlite` · `gunicorn` · `google-generative-ai` · `gemini-2.0-flash` · `chromadb` · `sentence-transformers` · `all-minilm-l6-v2` · `plotly` · `qrcode` · `pillow` · `werkzeug` · `open-meteo-api` · `render` · `html5` · `css3` · `javascript`

---

## What's next for WildNest

- **Native mobile app** with camera-first WildSight scans and offline log capture for field rescues.
- **Multi-organization support** — the current data model already has an `organization` field on User; the next step is org-scoped dashboards and role-based access (director / vet / volunteer).
- **Community verification** — let experienced adopters and vets verify each other's profiles, so the AI matching score can be weighted by trust.
- **Public API + webhooks** — so partner shelters can push intake data into WildNest and pull rehoming statistics back out.
- **Vaccination reminders as calendar invites** — auto-generated `.ics` files sent by email, so alerts survive a lost phone.
- **Longitudinal outcome tracking** — a year after adoption, ping the new owner: is the animal still with you? still healthy? This is the metric no rescue platform tracks today, and it is the one that matters most.

WildNest exists so that the next rescued sulcata tortoise, ball python, or bearded dragon is never lost in the system again.
