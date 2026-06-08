```markdown
# Candidate 3: Kristian Diana
**McMaster University · Software & Biomedical Engineering**
**Software Developer Intern @ RBC Amplify (current)**

> 🎯 **Watch for:** Can the team lead become a systems thinker?

**Profile:** Led a 10-person development team at GDG McMaster. Presented RL agent at CUCAI 2025 (300+ attendees). Built a RAG system that reduced token usage by 45%. Currently Software Developer intern at RBC Amplify. Leadership profile is genuinely rare in interns. Risk: strengths skew organizational and frontend-leaning (TypeScript, React, Firebase). Stress-test whether AI instincts match the leadership confidence.

---

# TECHNICAL SECTION — URL Shortener + AI Layer (30 min)

## Potential Starter Code to Give Kristian (if needed)

```python
import hashlib
from typing import Optional

class URLShortener:
    def shorten(self, long_url: str) -> str:
        """
        Given a long URL, return a short code (6–8 characters).
        The same long URL must always return the same short code.
        Must handle hash collisions.
        """
        pass

    def resolve(self, short_code: str) -> Optional[str]:
        """
        Given a short code, return the original long URL.
        Return None if the short code does not exist.
        """
        pass

```

**Example to walk her/him through:**

```python
shortener = URLShortener()
code1 = shortener.shorten("[https://www.anthropic.com/research/claude](https://www.anthropic.com/research/claude)")
print(code1)            # e.g. "a3f9bc"

code2 = shortener.shorten("[https://www.anthropic.com/research/claude](https://www.anthropic.com/research/claude)")
print(code1 == code2)   # True — same URL always returns same code

original = shortener.resolve(code1)
print(original)         # "[https://www.anthropic.com/research/claude](https://www.anthropic.com/research/claude)"

missing = shortener.resolve("xxxxxx")
print(missing)          # None

```

---

## Technical Q1 — "What's your collision resolution strategy and why?"

**🟢 Strong Hire**

> *"I'd hash the long URL with SHA-256, take the first 6–8 characters of the base62-encoded output, and check for collision in the database. On collision I'd either append a counter suffix or re-hash with a salt — counter is simpler and predictable. For very high throughput I'd pre-generate a pool of valid short codes offline so code generation is never on the critical path at request time."*

**🔵 Hire**

> *"I'd hash the URL and take a substring as the short code. If there's a collision I'd regenerate with slightly different input until I find a clean one."*

**🔴 No Hire**

> *"I'd use a random string generator and check if it already exists in the database. If it does, generate a new one."*

---

## Technical Q2 — "How do you make the AI slug generation async without blocking the user?"

**🟢 Strong Hire**

> *"The short code is returned immediately — that path is synchronous and fast. Slug generation kicks off as a background job: a task queue like Celery with Redis calls an LLM to summarize the page content and suggest a slug. The UI shows the short code right away and updates with the human-readable slug when it's ready — optimistic UI. Crucially, if slug generation fails, the short code still works. The AI layer is an enhancement, not a dependency."*

**🔵 Hire**

> *"I'd make the slug generation a separate async function that runs after the main response is sent. The user gets their short link first and the slug gets added later."*

**🔴 No Hire**

> *"I'd wait for the AI to finish generating the slug before returning the response to the user."*

---

## Technical Q3 — "Your RAG system reduced token usage by 45%. How did you measure that? What did you give up?"

*After they answer, redirect: "Forget the AI slug layer. What's your scaling strategy if this shortener needs to handle 10 million requests per day?"*

**🟢 Strong Hire**
On RAG:

> *"I tracked average tokens per context window before and after. Pre-retrieval I was passing the full document corpus chunked into the prompt. Post-retrieval I was only passing the top-3 relevant chunks. What I gave up was some recall — occasionally the right chunk wasn't in the top-3. I tuned the retrieval threshold and added a fallback: if no chunk scored above 0.7 cosine similarity, expand to top-5."*

On redirect:

> *"10 million requests a day is roughly 115 requests per second sustained, more at peak. I'd put redirect logic behind a load balancer, cache the most popular short codes in Redis for hot key optimization, and use read-only DB replicas for lookups. The write path — creating new URLs — is much lower volume so I'd keep that on the primary."*

**🔵 Hire**
On RAG:

> *"I compared token counts before and after implementing retrieval. The reduction came from only using the relevant parts of the documents instead of everything."*

On redirect:

> *"I'd add caching and maybe use a CDN for popular links."*

**🔴 No Hire**
On RAG:

> *"The 45% reduction was from using retrieval instead of passing all the documents to the model."*

On redirect:

> *(No concrete numbers. No architecture. "Scale the servers.")*

---

## Technical Scorecard

| Question | Strong Hire | Hire | No Hire |
| --- | --- | --- | --- |
| Collision resolution | SHA-256 + base62, counter fallback, pre-generated pool for throughput | Hash + substring, "regenerate" on collision — breaks at scale | Random string generation — uncontrolled collision probability |
| Async AI slug | Short code sync, slug via task queue, graceful degradation, optimistic UI | Right idea, no mechanism named, no degradation plan | Blocks response on LLM generation — doesn't understand async |
| RAG metric defense + scaling | Real measurement, recall trade-off, threshold tuning; specific rps + Redis + read replica on redirect | Vague on both — "compared token counts"; "caching + CDN" | Can't defend metric from own resume; no scaling architecture |

---

# BEHAVIOURAL SECTION (15 min)

## Behavioural Q1 — "You've led a 10-person team. How do you model asking for help to your team? And when do you personally ask for help?"

**🟢 Strong Hire**

> *"I was deliberate about this with GDG. Early on I noticed people would sit stuck rather than ask, so I started opening every sprint by sharing something I didn't know that week and had to look up — just to normalize it publicly. For myself I time-box: 45 minutes of genuine effort, then I ask. But I always come with what I tried and my current hypothesis. I've come to think of asking well as a skill — a bad question wastes everyone's time, a good question teaches both of you."*

**🔵 Hire**

> *"I try to encourage my team to ask questions and not be afraid to not know things. For myself I usually research first and go to my manager if I'm really stuck."*

**🔴 No Hire**

> *"I think asking for help is important and I tell my team it's okay. Personally I'm pretty self-sufficient so I usually just figure things out myself."*

---

## Behavioural Q2 — "Tell me about a time your technical approach was overruled. How did you handle it?"

**🟢 Strong Hire**

> *"At TrafficLightRL I wanted to use a custom reward function based on throughput optimization. My faculty advisor overruled it — insisted on a CO2 emission proxy because it was more defensible academically for the CUCAI paper. I disagreed at the time. I implemented their approach, but I also ran my version in parallel and documented both results. In the end their metric told a cleaner story for that conference audience. I updated my thinking: the audience matters as much as the technical correctness. I carry that into how I communicate AI work now."*

**🔵 Hire**

> *"A senior developer on the GDG project suggested a different architecture than what I had planned. I wasn't fully convinced but I went with it and it worked out fine."*

**🔴 No Hire**

> *"I've generally been trusted to make the technical calls on my projects, so this doesn't really come up much."*

---

## Behavioural Q3 (Tailored) — "You presented at CUCAI to 300 people. Now imagine presenting the same AI work to a risk committee at a bank — no technical background, very high stakes. What changes?"

**🟢 Strong Hire**

> *"Almost everything changes. At CUCAI I could say 'reward function' and 'Stable-Baselines3' and the room followed. A risk committee doesn't care about the model. They care about three things: what could go wrong, how do you know when it's going wrong, and what's the fallback. So I'd reframe the whole thing. Instead of 'our agent reduced CO2 by 12%' I'd say 'in simulation, the system made decisions that would reduce emissions by 12% — here's what the simulation can and can't tell us, and here's what happens if the model makes a bad decision in production.' And I'd anticipate the 'what if it's wrong' question before they ask it — at a bank that question is always coming."*

**🔵 Hire**

> *"I'd avoid technical jargon and explain things in plain language. I'd focus on the outcomes and business value rather than how the model actually works."*

**🔴 No Hire**

> *"I'd make the slides simpler and use more visuals and analogies to explain the technical concepts in a way non-technical people can understand."*

---

## Behavioural Scorecard

| Question | Strong Hire | Hire | No Hire |
| --- | --- | --- | --- |
| Modeling help-seeking | Led by example at GDG sprints, time-box rule, frames asking as a skill | Says right things, no mechanism, no specific team story | "Pretty self-sufficient" while leading a team — models not asking |
| Being overruled | Implemented decision + ran parallel test + updated thinking + lasting lesson about audience | Complied, it worked, no engagement with the challenge itself | "Trusted to make the calls" — not genuinely overruled |
| CUCAI → bank risk committee | Immediate audience reframe: failure modes, detection, fallback, anticipates "what if it's wrong" | "Plain language + business value" — right direction but surface level | Thinks about slide design, not the audience's actual concerns |

---

## Closing Question

> *"You have a GDG community and 50+ contributors you've onboarded. How would you bring that community-builder energy into a team of 5 at an AI lab?"*

**Strong answer:** Distinguishes crowd leadership from close-team dynamics — talks about 1:1 investment, psychological safety at small scale, knowledge sharing rituals.
**Weak answer:** "I'd just treat the team like a mini community." No distinction between leading 50 and leading 5.

```

```