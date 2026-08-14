# 🎬 WildNest — Demo Video Script

**Target runtime:** ~5:30 – 6:00 (aim for under 6 minutes; don't rush)
**Star of the demo:** Milo — a 1-year-old Golden Retriever rescued in Dhaka on June 2, 2026
**Speaking pace:** ~140 words/minute — clear, warm, unhurried
**Recording tool:** OBS Studio at 1920×1080, 30fps
**Voice:** Tell a story. You're introducing Milo to the world.

---

## 🛠️ Before you hit record

1. Start the app: `./venv/Scripts/python.exe app.py`
2. Open browser at `http://127.0.0.1:5000` — full screen, no bookmarks bar, zoom to 110%
3. Have a **dog photo** ready on your Desktop for the WildSight scan (a Golden Retriever ideally)
4. Log in ONCE as `maya.rescue@gmail.com` / `demo1234`, open Milo's chat, send one test message to warm up the embedding model (first call takes 20-40s). Then log out.
5. **Do not save any `.py` files after this point** — Flask's debug reloader restarts the server on every file change, bringing back the 20-40s AI delay right when you're recording
6. Do one full practice run WITHOUT recording — smooths out clicks and pacing
7. Close all other tabs, silence notifications, close Discord/Slack

---

## 📋 Scene-by-Scene Script

Every scene has:
- **🖱 ACTION** — exactly what you click / show
- **🎙 SAY** — the exact words you narrate

---

### SCENE 1 — Hook & Problem
### 🕐 ~25 seconds

**🖱 ACTION:**
Open with the **login page**. Do NOT log in yet. Let the animated paws visibly drift across the background. Camera stays still.

**🎙 SAY:**
> "Every year, millions of animals — dogs, cats, tortoises, parrots, reptiles — pass through rescue centers. And most of their journey lives on paper. Lost logbooks. Missed vaccinations. Mismatched adoptions. Forgotten medical history. WildNest fixes that. One AI-powered platform that follows every rescued animal from intake, through recovery, to the right forever home."

---

### SCENE 2 — Login & Dashboard
### 🕐 ~30 seconds

**🖱 ACTION:**
1. Click the email field — type `maya.rescue@gmail.com`
2. Type `demo1234` in password
3. Click **Log in**
4. Dashboard loads — Milo at the top, then Luna, then Kilo, then the rest
5. Slowly scroll down so the environmental charts come into view for one animal
6. Hover over a chart data point so a Plotly tooltip appears
7. Scroll back to the top

**🎙 SAY:**
> "This is Maya. She runs a small rescue in Dhaka. When she logs in, she sees every animal in her care — the ones she's rescued, the ones she's still tending, the ones ready for adoption — all in one place. Beside each name is a live snapshot of that animal's health, drawn from real daily logs. And today, we're following just one of them. Meet Milo."

---

### SCENE 3 — Milo's Profile & Environmental Logs
### 🕐 ~40 seconds

**🖱 ACTION:**
1. Click **Milo's** card
2. His profile opens — photo, species, age, rescue date, background at the top
3. Scroll down slowly to show his stress triggers and dietary requirements
4. Continue scrolling to reveal the six environmental charts (temperature, humidity, feeding, weight, stress, activity)
5. Pause briefly on the feeding chart and the weight chart
6. Scroll back up

**🎙 SAY:**
> "This is the animal profile page — the heart of WildNest. At the top: full identity — photo, species, breed, age, sex, and origin, whether rescued or personal. Below that: the rescue record — where the animal came from, when, and why. Then the care baseline — known stress triggers, dietary requirements, medical background. And down here: six live charts, one for each tracked dimension — temperature, humidity, feeding, weight, stress, and activity — every entry timestamped, plotted, and fully interactive. From this one page, Maya can log a new observation, run an AI health scan, generate a meal plan, open the passport, or start a chat. Milo's entire life, in one screen."

---

### SCENE 4 — Environmental Logging
### 🕐 ~20 seconds

**🖱 ACTION:**
1. On Milo's profile, click **Log Environment** or the "New Entry" button
2. The logging form opens — hover through the fields briefly (temperature, humidity, feeding, weight, stress, activity, photo/video upload)
3. Do NOT submit — just show the form
4. Click back / close the form

**🎙 SAY:**
> "Logging takes seconds. Maya enters today's temperature, feeding, weight, activity level — and she can even attach a photo or a short video of any unusual behavior. Every entry is validated at the database level, so bad data can never sneak in. And every entry becomes fuel for the AI systems we're about to see."

---

### SCENE 5 — Medical History & Vaccination Alerts
### 🕐 ~30 seconds

**🖱 ACTION:**
1. On Milo's profile, click **Medical History** or the medical tab
2. The medical page loads — Milo's vaccination and his head injury record from Dhaka Medical College Hospital are visible
3. Point cursor at the **overdue vaccination alert** at the top (Milo's vaccination is past due)
4. Scroll to show both records with dates and vet names
5. If there's an "Add Record" button, hover over it briefly

**🎙 SAY:**
> "Beyond daily logs, Milo has a complete medical timeline. Every visit, every treatment, every vet — recorded here. And WildNest tracks vaccination cycles automatically. See this red alert? Milo's rabies vaccine is overdue — WildNest flagged it, put an emergency notification on Maya's dashboard, so she can never forget. No missed doses. No slipped-through-the-cracks care."

---

### SCENE 6 — WildSight AI Health Analysis
### 🕐 ~35 seconds

**🖱 ACTION:**
1. Go back to Milo's profile
2. Click **WildSight AI** (or the health scan button)
3. Click the upload area, select your prepared dog photo
4. Wait 3-6 seconds for the analysis to appear — narrate over the wait
5. When the response arrives, scroll slowly so the severity badge and findings are readable

**🎙 SAY:**
> "This is WildSight — Milo's personal AI health analyst. It knows Milo. It's studied every log Maya has recorded, his medical history, his stress triggers, his weight trend. So when Maya uploads a photo, WildSight doesn't guess like a generic scanner would — it interprets what it sees through everything it already knows about Milo, and gives back a clear severity tier: normal, watch, contact staff, or emergency. Fifteen seconds. And Maya just got another friend besides milo"

---

### SCENE 7 — AI Chat with Milo's Assistant
### 🕐 ~35 seconds

**🖱 ACTION:**
1. Click the **Chat** tab or button on Milo's profile
2. Type: `Milo has been very restless during thunderstorms. What can I do to help him?`
3. Press Enter, wait for the response to appear
4. Once it finishes, scroll to reveal the **cited source** at the bottom
5. Hover the cursor briefly over the citation

**🎙 SAY:**
> "And Maya can talk to Milo's AI directly. Any question, any time — from thunderstorm anxiety to feeding routines to whether a symptom needs a vet. It's a real conversation, not a search bar. And watch this — when the answer draws on published care references, it cites the exact source. So Maya isn't guessing which advice on the internet to trust. She has a species specialist on speed dial, and it shows its work."

---

### SCENE 8 — Weather-Aware Meal Plan
### 🕐 ~25 seconds

**🖱 ACTION:**
1. Click **Meal Plan** on Milo's profile
2. If a plan exists, show it. If not, click **Generate Plan** and wait ~4 seconds
3. Point cursor at the **weather summary** at the top (Dhaka temperature and humidity)
4. Then point at the actual meal suggestions

**🎙 SAY:**
> "Milo needs to eat differently on a hot Dhaka afternoon than on a mild morning. So WildNest checks the real weather at his location — live — and generates today's meal plan around it. Breakfast, lunch, dinner, and care tips. Personalized to Milo, tuned to the weather outside his window, refreshed every single day."

---

### SCENE 9 — QR Passport
### 🕐 ~25 seconds

**🖱 ACTION:**
1. Click **Passport** on Milo's profile
2. The passport page opens with Milo's QR code prominent
3. Point cursor at the QR code
4. *(Optional — powerful if you can pull it off)* Hold your phone up briefly to scan the QR — Milo's public passport opens on the phone screen

**🎙 SAY:**
> "If Maya ever hands Milo off — to a vet, another shelter, an adopter — she just shows this. Milo's passport. A single QR code. Anyone can scan it, and instantly see who he is, his medical history, and how to care for him. No login. No app install. Just a secure link that works from any phone camera in the world."

---

### SCENE 10 — Notifications
### 🕐 ~20 seconds

**🖱 ACTION:**
1. Click the **bell icon** in the top navbar
2. The notification dropdown opens — show the mix: transition notes, vaccination alerts, emergency flags
3. Point cursor at the red emergency badge if visible
4. Click one notification to open it fully so the text is readable

**🎙 SAY:**
> "Everything WildNest learns about Maya's animals flows into one notification stream. Overdue vaccines flag red as emergencies. Daily updates about newly adopted pets arrive automatically. Nothing about her animals slips through the cracks — because Maya can't be everywhere, but WildNest is."

---

### SCENE 11 — Rehoming Feed
### 🕐 ~25 seconds

**🖱 ACTION:**
1. Click **Feed** in the top navigation — leave Milo's profile
2. The browse page loads. Let viewers see the listed animals (Rex the iguana, Kilo the tortoise, and pusu the cat)
3. Scroll through the cards
4. Optionally use the species filter to show it filters live

**🎙 SAY:**
> "When an animal is ready for a permanent home, it moves to the rehoming feed. Any adopter, anywhere, can browse the animals waiting — filter by species, read their stories, see their real health data. Every listing is transparent — the same environmental charts and medical history that Maya sees are visible to any potential adopter."

---

### SCENE 12 — AI-Powered Adopter Matching
### 🕐 ~35 seconds

**🖱 ACTION:**
1. On the feed page, click **Find My Match**
2. Fill in:
   - Experience: `Intermediate`
   - Space: `Apartment with a dedicated pet room`
   - Species: `Open to any`
   - Time: `2-3 hours/day`
   - Location: `Dhaka, Bangladesh`
3. Click **Get Matches** and wait ~5 seconds
4. When results appear, scroll to show the compatibility scores and AI-written reasons per pet

**🎙 SAY:**
> "But browsing isn't matching. So WildNest goes further. An adopter tells us about themselves — their experience, their living space, their climate, their available time. And WildNest scores every listed animal for compatibility, with a written reason for every single score. Why this tortoise fits. Why this iguana doesn't. So adopters don't just find a pet. They find the right pet — and animals go to homes where they'll actually thrive."

---

### SCENE 13 — Handover & Transition Notifications
### 🕐 ~30 seconds

**🖱 ACTION:**
1. Navigate to one of the transferred animals (e.g., picu2 or Kilo)
2. Show the handover certificate — the unique certificate ID, from-user, to-user, date
3. Then click the **bell icon** again
4. Show one of the "It's my Xth day with you" transition notifications — click to open it fully

**🎙 SAY:**
> "And when a match becomes an adoption, WildNest generates a formal handover certificate — a unique ID, digitally transferring ownership, with a printable record for both sides. But the story doesn't end there. For the first thirty days in the new home, the adopter receives daily notes — written by WildNest, in the animal's own voice — sharing how it's settling in, what it misses from before, what it needs today. Because a rescue isn't complete when the adoption is signed. It's complete when the animal feels at home."

---

### SCENE 14 — Closing
### 🕐 ~10 seconds

**🖱 ACTION:**
1. Click the WildNest logo to return to the dashboard
2. Let the animated paws drift one final time
3. Fade to black on the last word

**🎙 SAY:**
> "WildNest. From rescue, to recovery, to rehome. Every animal — every story — remembered."

---

## 🎯 Delivery Checklist

Tape this next to your monitor before you record:

- ✅ **Breathe between scenes** — a half-second pause reads as confidence
- ✅ **Never say "um"** — if you flub, restart the SCENE, not the whole video
- ✅ **Cursor should be intentional** — no aimless mouse-wandering while you talk
- ✅ **Wait for AI responses to finish loading before speaking about them**
- ✅ **Say Milo's name warmly** — you're telling his story, not describing a feature
- ✅ **Record narration separately** if your keyboard is loud — Audacity, then layer in DaVinci Resolve
- ✅ **Add captions** for anything AI-generated — helps judges watching muted

---

## ⏱ Scene Timing Cheat Sheet

| Scene | Feature | Duration |
|-------|---------|----------|
| 1. Hook | Problem statement | ~25s |
| 2. Login → Dashboard | Meet Maya, see all animals | ~30s |
| 3. Milo's profile + charts | Introduce Milo, show env logs | ~40s |
| 4. Logging | Show how easy logging is | ~20s |
| 5. Medical + vaccine alerts | Medical timeline + auto-alerts | ~30s |
| 6. WildSight AI | Photo-based health scanner | ~35s |
| 7. AI Chat | Conversation with Milo's assistant | ~35s |
| 8. Meal Plan | Weather-aware daily plan | ~25s |
| 9. QR Passport | Portable digital identity | ~25s |
| 10. Notifications | Central alert stream | ~20s |
| 11. Rehoming Feed | Public listings | ~25s |
| 12. AI Matching | Compatibility scoring | ~35s |
| 13. Handover + Transition Notes | Certificate + first-person notes | ~30s |
| 14. Closing | | ~10s |

**Total: ~6:05** — comfortable, not rushed. Fine for a demo submission.

---

## 🎤 Delivery tips per scene

- **Scene 1:** Slow, deliberate, almost sad — you're describing a problem. Let it land.
- **Scene 2:** Warm up — introduce Maya as a real person.
- **Scene 3:** Slow down on "Meet Milo" and his age. Let viewers connect.
- **Scene 4:** Practical, quick — this is a "look how simple" moment.
- **Scene 5:** Slight urgency — the "red alert" moment sells care.
- **Scene 6:** Confident — you know this AI is smart. Say it like you know.
- **Scene 7:** Warm and technical — this is your smartest feature.
- **Scene 8:** Playful — "hot Dhaka afternoon" should land with a smile in your voice.
- **Scene 9:** Practical, matter-of-fact — this feature sells itself.
- **Scene 10:** Reassuring — "nothing slips through the cracks."
- **Scene 11:** Building — the platform's vision widens here.
- **Scene 12:** Confident — this is the "wow" scene for judges.
- **Scene 13:** Soft, warm — this is the emotional heart. Slow way down.
- **Scene 14:** Final line, spoken with quiet pride. Let the paws animate out.

---

## 💡 If a scene doesn't go as planned

- If AI takes >10 seconds to respond, just narrate the wait: "the AI's looking through Milo's history now..."
- If you flub a word, pause 2 seconds, restart the sentence
- If you click the wrong button, don't panic — narrate the recovery: "let me jump back to..."
- Judges know demos aren't perfect — smooth recovery reads as competence

---

## 🎬 Post-production polish (30 minutes, huge payoff)

- Add a **1-second title card** at 0:00 with "WildNest" and your logo
- Add a **soft background track** — royalty-free from Pixabay Music (search "uplifting corporate ambient" — instrumental, at ~40% volume under your voice)
- **Fade in and out** on both audio and video for the first and last second
- Add captions with **DaVinci Resolve's auto-caption** (free) — huge for judges watching muted
- Consider a **speed ramp** on any 4-6 second AI loading gap (1.5×) so it doesn't feel dead

Good luck. Milo's story is worth telling well.
