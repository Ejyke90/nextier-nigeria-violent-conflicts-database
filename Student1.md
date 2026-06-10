# Engineering Co-op – Fall 2026 Interview Kit

**Interviewed by:** Ejike Udeze ⭐ Strong Yes

**Candidate:** Anas Almasri

**Role:** RBC Assist — Personal Grounding (PG) Intelligence Team

**Overall Recommendation:** ✅ **Strong Hire** for RBC Assist Personal Grounding Team

---

## Key Take-Aways

> **Strong Hire** for RBC Borealis — RBC Assist Personal Grounding Team
>
> Anas demonstrated strong engineering fundamentals and an impressive ability to think through system design before writing a single line of code. He produced a fully correct rate limiter implementation with all five expected outputs returning accurately (`True, True, False, True, False`), matching the specification exactly. He is a clear communicator, proactively coachable, and showed the independence and structured thinking we need on the PG Intelligence team.

---

## Coding Problem: In-Memory Rate Limiter

**Problem:** Design a `RateLimiter` class that limits API requests per client using a sliding time window.

**Specification:**
- A client is identified by a unique `client_ref_id` (string)
- A client can make up to `max_requests` within any sliding `time_window_seconds`
- `is_allowed(client_ref_id, timestamp) → bool`: returns `True` if request is allowed, `False` if limit exceeded
- Timestamps are monotonically increasing integers (seconds)
- The window includes the current timestamp and extends backwards

**Test Cases & Results:**

| Call | Expected | Anas's Output |
|---|---|---|
| `limiter.is_allowed("user_1", 1)` | `True` | ✅ `True` |
| `limiter.is_allowed("user_1", 5)` | `True` | ✅ `True` |
| `limiter.is_allowed("user_1", 6)` | `False` | ✅ `False` |
| `limiter.is_allowed("user_1", 11)` | `True` | ✅ `True` |
| `limiter.is_allowed("user_1", 12)` | `False` | ✅ `False` |

**Result: 5/5 — All test cases passed correctly.**

---

## Interview Questions and Answers

---

### Question 1: Did the candidate understand the problem?

*To solve a problem, you need to first gather context and requirements then break the problem down into manageable pieces. A great candidate won't be afraid to take the time at the beginning of the session (and throughout) to understand the problem and ask clarifying questions.*

- Could the candidate describe the problem and solution in a way that someone without significant domain knowledge could understand?
- Did they ask questions and clarify the requirements so they could get started on working towards a potential solution?

---

**Strong Hire (4)**

Anas began the session by methodically reading through the problem specification before writing any code. He broke it down into its core components — the sliding window logic, the per-client state storage, and the edge case of the window boundary being inclusive on both ends.

He asked targeted clarifying questions: specifically whether timestamps could repeat and whether the window boundary was inclusive or exclusive. He did not assume — he confirmed.

He approached the problem as an independent systems thinker, identifying that the key challenge was the sliding window (not a fixed bucket) and immediately reasoned through the data structure needed to support O(n) window scans over a client's timestamp list.

He came up with a working, strong, tangible solution.

---

### Question 2: Did the candidate articulate their thoughts well?

*All projects at RBC Borealis are complex and are done as part of a team. A strong candidate will bring you along with them as they discuss solutions. The ability to clearly communicate about projects is just as important as understanding their details.*

- Could the candidate effectively articulate their thought process throughout the session?
- Did the candidate have conviction in their approaches?
- Could they describe problems and solutions in a way that someone without significant domain knowledge could understand?

---

**Strong Hire (4)**

Anas narrated his approach in real time as he coded. He explained why he chose a dictionary keyed by `client_ref_id` (O(1) lookup per client), and clearly articulated the window filtering logic before implementing it.

He acknowledged the limitation of his approach — that storing all timestamps per user is unbounded in theory — and proactively noted that in a production system he would add a TTL eviction strategy or use a bounded deque. This level of self-aware technical reasoning is rare in co-op candidates.

He was never silent. Every design decision came with a spoken rationale, and when I introduced a constraint mid-session, he pivoted clearly and explained how it affected his approach.

---

### Question 3: Is the candidate coachable?

*We want interns at RBC Borealis who are coachable! While we want them have familiarity with coding and programming, we are identifying potential as well. A strong candidate seeks out and responds well to feedback.*

- Did the candidate respond well to feedback and seek out feedback?
- Do you think the candidate could take input from others and use that as a valuable tool in their development?
- Did the candidate demonstrate a willingness to take action and make changes based on feedback?
- Did the candidate seem open to feedback?

---

**Strong Hire (4)**

I believe Anas is highly coachable. When I introduced a wrench to his logic mid-session — questioning whether his window filtering condition correctly handled the inclusive lower bound — he paused, reasoned it through out loud, and confirmed his implementation was correct while explaining exactly why.

He actively asked for feedback at key inflection points rather than waiting to be told. He treated the session as a collaborative dialogue, not a solo performance. That is exactly the mindset we need on a team building the PG Intelligence platform where requirements evolve week to week.

---

### Question 4: Behavioural / Hiring Manager Questions

*These are recommended sample questions for the Behavioural / Hiring Manager portion. We recommend questions that gauge how an intern handles difficult situations, collaboration, and giving and receiving feedback.*

---

**Q1: How comfortable are you with asking for help? (Alternative: When was the last time you asked for help?)**
- Follow-up: What do you find challenging about seeking help from others?
- Follow-up: How comfortable are you asking for help?

**Strong Hire (4)**

Anas identified clearly when he needs to ask for help versus when he should push through independently. He gave a specific example from a group project where he unblocked himself for 30 minutes before raising the issue to a team lead — demonstrating the right balance between autonomy and escalation. He identified that asking for help is sometimes uncomfortable for him but he has developed a concrete strategy: time-boxing his solo attempts before escalating.

---

**Q2: How would you respond to receiving difficult feedback? (Alternative: When was the last time you received difficult feedback?)**
- Follow-up: What steps would you take if you learned you were not meeting expectations in your internship?

**Strong Hire (4)**

Anas described a specific instance where a professor gave him critical feedback on the architecture of a project. Rather than defend his approach, he listened fully, asked clarifying questions about what success would look like, and came back with a revised design. He identifies what support he needs and makes a plan — exactly the loop we want interns running on the PG team.

---

**Q3: What do you think is going to be the most challenging part of this Internship for you?**
- Follow-up: What do you think is going to be easy for you?
- Follow-up: How do you plan to overcome the challenges you see ahead for yourself?

**Strong Hire (4)**

Anas was forthright. He acknowledged that operating inside a regulated financial institution — where every system decision has compliance and security implications — will be a new context for him. He has a plan: he intends to front-load his learning on RBC tooling and ask questions early rather than assume. He correctly identified his strength as algorithmic thinking and rapid prototyping, and named the gap honestly.

---

### Question 5: During the interview, what skills (or experiences) did the candidate show to exhibit their ability to have an impact on your team?

Anas showed strong competence across all key areas:

**Software:** Solid grasp of Python, data structures, and algorithm design — especially sliding window and dictionary-based state management patterns directly relevant to PG's memory layer work.

**Problem Solving:** Anas considers tradeoffs before committing to an implementation. He thinks end-to-end and correctly identified production-scale limitations of his solution without prompting.

**Communication:** Narrated every decision clearly in real time. Could explain his solution to a non-technical stakeholder without losing precision.

**Leadership:** Drove the coding session independently. Asked for feedback proactively rather than waiting for it. Never silent.

---

## Focus Attributes

| Attribute | Assessment |
|---|---|
| Code is written in a clear, concise manner, and can be easily understood by readers | ⭐ Strong |
| Asks questions to resolve uncertainties and establish requirements | ⭐ Strong |
| Proactively identifies edge cases and production limitations | ⭐ Strong |
| Coachable — adapts approach when given feedback mid-session | ⭐ Strong |

---

## Final Recommendation

**✅ Strong Hire — RBC Assist Personal Grounding (PG) Intelligence Team**

Anas is a strong independent thinker with the communication skills and coachability to thrive in a fast-moving team building enterprise AI infrastructure. His rate limiter solution was flawless (5/5 test cases), his reasoning was systematic, and his self-awareness about production tradeoffs signals a candidate who will grow fast. He is ready for the PG Intelligence platform on day one.
