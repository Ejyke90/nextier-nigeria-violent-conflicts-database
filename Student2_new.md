# Anas Almasri — Interview Guide
**University of Toronto · CS & Math Sciences**
**Incoming MongoDB Education Intern**

---

# PROBLEM: Thread-Safe Rate Limiter
**For: Anas Almasri**

---

## Your Task

Implement an in-memory rate limiter to prevent API abuse. Given a client ID and a timestamp, return whether the request is allowed based on a maximum request limit within a sliding time window.

> 🎯 **Watch for:** Can he think beyond the model layer into real software systems?

**Profile:** Robotics ML researcher with PyTorch and MuJoCo experience. Built a real-time training dashboard with WebSockets and Socket.io, and a multi-agent pipeline with FastAPI and Redis. Strong model-side instincts. The probe is whether he can reason about the software systems underneath — data structures, state management, concurrency, and API design — when there is no ML to lean on.

**Languages on resume:** Python, JavaScript, Java, C++
**Frameworks:** FastAPI, Flask, React Native, LangChain, Redis, Socket.io, PyTorch

---

# TECHNICAL SECTION — Rate Limiter + Backend Architecture (30 min)

## Starter Code (hand to candidate)

```python
"""
Design an in-memory rate limiter to prevent API abuse.

Rules:
- A client is identified by a unique client_id (string).
- A client can make up to `max_requests` within any sliding `time_window_seconds`.
- is_allowed(client_id, timestamp) → returns True if the request is allowed, 
                                     returns False if the limit is exceeded.

Note: 
- To make testing easy, the current time is passed in as `timestamp` (an integer in seconds). 
- You can assume timestamps are monotonically increasing (time always moves forward).
- A time window includes the current timestamp and extends backwards. 
  (e.g., if window is 10s and current time is 15s, the window covers > 5s up to 15s).

Example:
    limiter = RateLimiter(max_requests=2, time_window_seconds=10)

    limiter.is_allowed("user_1", 1)  # Returns True
    limiter.is_allowed("user_1", 5)  # Returns True 
    limiter.is_allowed("user_1", 6)  # Returns False (Limit of 2 reached)
    limiter.is_allowed("user_1", 11) # Returns True (t=1 expired, window is t > 1)
    limiter.is_allowed("user_1", 12) # Returns False (t=5 and t=11 are still in window)
"""

class RateLimiter:
    def __init__(self, max_requests: int, time_window_seconds: int):
        pass

    def is_allowed(self, client_id: str, timestamp: int) -> bool:
        pass

Test Cases (Interviewer Copy — Keep Hidden)
Run these assertions to verify the candidate's logic after they have tested it themselves. A strong intern should pass all of these within 20–25 minutes.

def run_tests():
    limiter = RateLimiter(max_requests=2, time_window_seconds=10)

    assert limiter.is_allowed("user_1", 1) == True, "Failed: 1st request should be allowed"
    assert limiter.is_allowed("user_1", 5) == True, "Failed: 2nd request should be allowed"
    assert limiter.is_allowed("user_1", 6) == False, "Failed: 3rd request inside window should be denied"
    assert limiter.is_allowed("user_1", 11) == True, "Failed: Oldest request expired, should be allowed"
    assert limiter.is_allowed("user_2", 11) == True, "Failed: user_2 should have an independent limit"
    assert limiter.is_allowed("user_1", 12) == False, "Failed: Limit of 2 reached (t=5, t=11)"
    assert limiter.is_allowed("user_1", 15) == True, "Failed: Request at t=5 expired, should be allowed"

    print("All test cases passed! 🟢")

run_tests()

Expected Optimal Solution (Interviewer Copy)
Time Complexity: O(1) amortized per request.
Space Complexity: O(N) where N is the number of active requests in the window.

Python

from collections import defaultdict, deque

class RateLimiter:
    def __init__(self, max_requests: int, time_window_seconds: int):
        self.max_requests = max_requests
        self.time_window = time_window_seconds
        self.client_logs = defaultdict(deque)

    def is_allowed(self, client_id: str, timestamp: int) -> bool:
        log = self.client_logs[client_id]

        # 1. Evict timestamps strictly older than the sliding window
        window_start = timestamp - self.time_window
        while log and log[0] <= window_start:
            log.popleft()

        # 2. Check if under capacity
        if len(log) < self.max_requests:
            log.append(timestamp)
            return True
            
        return False

Technical Q1 — "Your code works perfectly for a single thread. But in our enterprise environment, this runs on FastAPI with multiple ASGI workers. Walk me through exactly where the race condition happens in your is_allowed function if two workers hit it at the exact same millisecond, and how you would fix it."
🟢 Strong Hire

"The race condition is on the capacity check. Thread A and Thread B both evaluate if len(log) < self.max_requests at the exact same time. They both see a length of 1, both decide it's under the limit of 2, and both append their timestamp. Now we have 3 requests recorded for a limit of 2. I would fix this by wrapping the eviction and append logic inside a threading.Lock() so it executes as an atomic operation."

🔵 Hire

"I'd use a lock to make the function thread-safe. Concurrent access to the dictionary by multiple workers can cause data corruption or allow too many requests through, so we need to acquire a lock at the start of the function and release it at the end."

🔴 No Hire

"Python has the Global Interpreter Lock (GIL) so threading isn't actually an issue. Only one thread can run at a time anyway." (Misunderstands that the GIL does not protect compound check-then-act operations).

Technical Q2 — "If we scale to 5 servers behind a load balancer, your in-memory dictionary is now siloed per server. You mentioned using Redis in your AIAI project. How would you redesign this state using Redis?"
🟢 Strong Hire

"I'd move the timestamp logs into Redis. A great approach is using Redis Sorted Sets (ZSET) where the key is the client ID, the score is the timestamp, and the value is also the timestamp. We'd use ZREMRANGEBYSCORE to drop old timestamps, ZCARD to check the limit, and ZADD to insert. To avoid race conditions across servers, I'd wrap those commands in a Lua script so Redis executes them atomically."

🔵 Hire

"I'd use Redis to store the request count. I could store the client ID as a key with an expiration time (TTL) equal to the time window, and just increment the counter. It's technically a fixed window rather than a sliding window, but it solves the distributed state problem."

🔴 No Hire

"I would just have the 5 servers talk to each other to share their dictionaries via an API." OR "I've only used Redis for basic caching, I'm not sure how to use it for counting."

 Question,Strong Hire,Hire,No Hire
Core Implementation,O(1) amortized via Sliding Window Log (deque + defaultdict); accurate eviction logic,Uses list + filter to clean old timestamps; works but less efficient,Fixed window counter; fails test cases; doesn't filter old timestamps
Thread-Safety Probe,Pinpoints exact check-then-act vulnerability; uses threading.Lock(),"""Add a lock"" generally; understands concurrent dict access is bad","""GIL handles it"" — incorrect understanding of concurrency"
Distributed State (Redis),Redis Sorted Sets (ZSET) for sliding window; mentions Lua script for atomicity,Redis key with TTL + increment counter (Fixed Window compromise),Peer-to-peer server syncing; no Redis data structure knowledge

BEHAVIOURAL SECTION (15 min)Behavioural Q1 — "You maintained 99% code coverage at Amicare during high-velocity 2-week sprints. Tell me about a time when a test caught a critical bug right before deployment, or alternatively, a time when a test was just 'security theater' and you had to push back on the 99% metric."🟢 Strong Hire"At Amicare, reaching 99% often led to testing implementation details rather than behaviours, which is classic security theater. However, it did catch a critical edge case: a timezone offset bug in the React components that was rendering patient appointment times incorrectly for users outside of EST. It changed how I view coverage: 99% is a vanity metric, but writing tests specifically for boundary conditions on data transformations is essential."🔵 Hire"We had a bug where the backend was trying to access a null value in the healthcare data, and my unit test caught it before it went to production. Getting to 99% was really tough during sprints but we prioritized writing the tests to keep the code quality high."🔴 No Hire"I honestly can't think of a specific bug. The tests usually just passed because I made sure the code was right the first time. The 99% was just a requirement we had to hit."Behavioural Q2 — "At Bitarco, you integrated QuickBooks and logistics APIs. Third-party APIs are notoriously unreliable. Tell me about a time an external API failed, rate-limited you, or sent malformed data in production. How did your system handle it?"🟢 Strong Hire"The logistics API we used would frequently rate-limit us during peak transaction hours. I handled it defensively. I implemented an exponential backoff retry mechanism, and if it still failed, the transaction was pushed to a dead-letter queue. This ensured the $6.6M platform didn't drop shipments permanently—they were just queued for reconciliation when the API recovered. You can never trust a third-party API to stay up."🔵 Hire"We got 500 errors from the QuickBooks API sometimes. I added a try/catch block around the integration so that if QuickBooks failed, it wouldn't crash our entire backend. We just logged the error so someone could fix it manually later."🔴 No Hire"The APIs were actually really stable while I was there so we didn't have any major outages. I just followed their documentation to set up the connections."Behavioural Q3 (Tailored) — "You built a stateful pipeline orchestrator for your AIAI project using a finite-state machine (FSM). Why an FSM instead of just a sequence of async functions or a standard DAG? What specific problem did it solve?"🟢 Strong Hire"Multi-agent ML pipelines rarely move in a straight line. They have loops and conditional branching—for instance, if an agent fails a validation check, it has to loop back and re-prompt the LLM. A standard Directed Acyclic Graph (DAG) handles cycles poorly, and basic async functions turn into spaghetti code. The FSM allowed explicit state transitions, making it trivial to track exactly where an agent was stuck via the WebSocket interface."🔵 Hire"The finite-state machine was a good way to keep the code organized. Since we had multiple agents doing different NLP tasks, the FSM made it easier to track which agent was currently working and manage the data ingestion."🔴 No Hire"I used an FSM because LangChain's documentation suggested it for agent pipelines, so I just followed the tutorial. I haven't really thought about comparing it to a DAG."Behavioural ScorecardQuestionStrong HireHireNo HireTesting vs. Velocity (Amicare)Identifies "security theater"; names specific boundary case (e.g., timezone) caught by testVague bug (null pointer); defends the 99% metric blindlyCan't name a bug; "code was right the first time"3rd-Party API Failure (Bitarco)Defensive architecture: exponential backoff, dead-letter queues, no dropped dataBasic try/catch block, manual loggingBlind trust in third-party uptime; no fallback logicFSM Architecture (AIAI)Justifies choice vs DAG: loops, conditional branching, LLM validation cycles, WebSocket debugging"Organized the code"; right direction but surface-level reasoning"Followed a tutorial"; no understanding of underlying trade-offs

Closing Question
"If you joined our team tomorrow, what's one thing about how we build software in an enterprise that you'd want to understand in your first week — and why?"

Strong answer: Asks about deployment pipelines, how failures/alerts are handled in production, CI/CD processes, or how engineering decisions are validated before going live.
Weak answer: Asks about generic tech stack choices (e.g., "what IDE do you use" or "do you prefer PyTorch or TensorFlow").
