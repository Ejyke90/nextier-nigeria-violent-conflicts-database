```markdown
# Candidate 1: Anas Almasri
**University of Toronto · CS & Math Sciences**

---

# PROBLEM 1: Task Scheduling System
**For: Anas Almasri**

---

## Your Task

You are building a task scheduling system. Tasks can depend on other tasks — a task can only run after all of its dependencies have completed.

> 🎯 **Watch for:** Can he go beyond ML research into system design?

**Profile:** Robotics ML researcher. PyTorch, MuJoCo, diffusion policies. Built an autonomous multi-agent AI project (LangChain, FastAPI, Redis, Socket.io). Heavy model-side experience — the probe is whether he can reason about the infrastructure and data layers underneath a model.

---

# TECHNICAL SECTION — Task Scheduling System (30 min)

## Starter Code to Give Anas

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class Status(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"

@dataclass
class Task:
    name: str
    priority: int                        # lower number = higher priority
    status: Status = Status.PENDING
    dependencies: list[str] = field(default_factory=list)

class TaskScheduler:
    def add_task(self, task: Task) -> None:
        """
        Register a task with the scheduler.
        Raise an error if adding this task would create a circular dependency.
        """
        pass

    def get_next_task(self) -> Optional[Task]:
        """
        Return the highest-priority task whose dependencies are all DONE.
        Return None if no task is currently runnable.
        """
        pass

    def mark_done(self, task_name: str) -> None:
        """Mark a task as DONE."""
        pass

    def mark_failed(self, task_name: str) -> None:
        """Mark a task as FAILED."""
        pass

```

**Example to walk him through:**

```python
scheduler = TaskScheduler()
scheduler.add_task(Task(name="load_data",   priority=1, dependencies=[]))
scheduler.add_task(Task(name="clean_data",  priority=2, dependencies=["load_data"]))
scheduler.add_task(Task(name="train_model", priority=3, dependencies=["clean_data"]))

next_task = scheduler.get_next_task()
# Expected: load_data — only task with no pending dependencies

scheduler.mark_done("load_data")
next_task = scheduler.get_next_task()
# Expected: clean_data — dependency now satisfied

```

---

## Technical Q1 — "Walk me through your data structure choice before writing any code."

**🟢 Strong Hire**

> *"I'd model this as a directed acyclic graph — tasks are nodes, dependencies are directed edges. I'd use an adjacency list to represent the graph and a min-heap priority queue for execution order. Before running anything I'd do a topological sort to validate there are no cycles and to get the correct execution sequence."*

**🔵 Hire**

> *"I'd use a dictionary mapping task names to their dependencies, and a separate dictionary for status. I'd iterate through tasks and check if all dependencies are marked done before running each one."*

**🔴 No Hire**

> *"I'd just keep a list of tasks and check the status field before running each one."*

---

## Technical Q2 — "What happens if there's a circular dependency? How do you detect it?"

**🟢 Strong Hire**

> *"During the topological sort I'd use DFS with three states: unvisited, in-progress, and done. If I encounter an in-progress node again during DFS, I've found a cycle. Critically, I'd check this at task registration time — fail fast, not at runtime when it's too late."*

**🔵 Hire**

> *"I'd keep track of which tasks I've already visited during traversal. If I see the same task again, that's a cycle."*

**🔴 No Hire**

> *"You'd probably get an infinite loop, so I'd add a timeout or a max retry count to stop it."*

---

## Technical Q3 — "How would you expose this as a REST API?"

*After they answer, redirect: "Let's simplify — forget priority for now, just get the dependency resolution working."*

**🟢 Strong Hire**
On API:

> *"FastAPI — POST /tasks to register, POST /tasks/{id}/run to trigger async execution backed by a Celery or Redis Queue worker, GET /tasks/{id} for status. Run would be async since tasks could be long-running."*

On redirect:

> *"Good call — let me nail dependency resolution first and layer priority back on top once that's solid." (Immediately productive, no frustration.)*

**🔵 Hire**
On API:

> *"I'd make a POST endpoint to create tasks and a GET endpoint to check their status."*

On redirect:

> *"Sure, okay." (Accepts but takes 20–30 seconds to mentally reset, loses thread briefly.)*

**🔴 No Hire**
On API:

> *"I haven't really thought about the API layer yet, I was focused on the logic."*

On redirect:

> *(Either ignores it and keeps working on priority, or abandons all prior context and starts over.)*

---

## Technical Scorecard

| Question | Strong Hire | Hire | No Hire |
| --- | --- | --- | --- |
| Data structure choice | DAG + adjacency list + topological sort, explained unprompted | Dict/list approach, correct logic, no cycle awareness | Flat list, no dependency modeling, jumps to code |
| Cycle detection | DFS 3-state coloring, fail-fast at registration time | Correct intuition, detects at runtime not build time | "Add a timeout" — structural problem treated as runtime problem |
| API design + redirect | FastAPI, async worker, graceful redirect with no frustration | Basic endpoints, accepts redirect but loses the thread | No API thinking; ignores or fully restarts on redirect |

---

# BEHAVIOURAL SECTION (15 min)

## Behavioural Q1 — "How comfortable are you with asking for help? Walk me through the last time you were blocked on something technical."

**🟢 Strong Hire**

> *"Pretty comfortable. In my ablation study work I was getting inconsistent results across simulation runs. I spent a full day debugging before I brought it to my supervisor. She spotted a seed initialization issue in five minutes. After that I set a personal rule: one focused hour, then I ask — but I come with what I tried and my current hypothesis, not just 'I'm stuck.'"*

**🔵 Hire**

> *"I'm getting more comfortable with it. I used to try to figure everything out myself but I've realized that's not always the fastest path. I remember being stuck on a PyTorch shape mismatch for a while and eventually asked a labmate."*

**🔴 No Hire**

> *"I usually figure things out on my own — Stack Overflow and the docs are almost always enough. I don't like to bother people if I can avoid it."*

---

## Behavioural Q2 — "Tell me about a time feedback changed the direction of something you were building."

**🟢 Strong Hire**

> *"In my AIAI project I built the orchestrator as a rule-based finite state machine — clean and predictable. A peer reviewed it and pointed out that adding any new pipeline stage meant touching five different files. I pushed back at first because it was working. But when they showed me what adding one stage would actually look like, I got it. I rebuilt it with a plugin architecture — took three days, but every stage after that took twenty minutes to add. The feedback was annoying to receive. It was also the best thing that happened to that project."*

**🔵 Hire**

> *"My supervisor suggested I try a different preprocessing approach. I thought mine was fine but I implemented their suggestion and it did perform better."*

**🔴 No Hire**

> *"I honestly can't think of a specific time where I had to change direction significantly. I usually get positive feedback on my work."*

---

## Behavioural Q3 (Tailored) — "Your AIAI project achieved 80% model accuracy. What would it take to reach 90%? And at what point do you decide it's not worth the effort?"

**🟢 Strong Hire**

> *"First I'd run an error analysis — where are the 20% failures clustering? Data quality issues? Edge cases in specific task types? Model capacity ceiling? Getting from 80 to 85 is usually a data problem — more labeled examples, better augmentation. Getting from 85 to 90 is usually a model architecture or training regime problem, which is more expensive. But the real question is what 90% is actually worth in production. If a 10% error rate means 10% of pipelines need human review, that might be cheaper than the engineering cost of closing the gap. I'd want to put a number on that before committing to the climb."*

**🔵 Hire**

> *"I'd look at the data first — maybe add more training examples or try augmentation. I'd also experiment with different architectures. At some point the gains start getting smaller and it's probably not worth continuing."*

**🔴 No Hire**

> *"I'd try different hyperparameters and maybe a larger model. You can always get higher accuracy if you train longer or use more data."*

---

## Behavioural Scorecard

| Question | Strong Hire | Hire | No Hire |
| --- | --- | --- | --- |
| Asking for help | Specific story, self-imposed time-box rule, framed as efficiency not weakness | Right direction, vague, no rule, "getting more comfortable" | "Don't bother people" — will go dark when blocked |
| Receiving feedback | Specific technical reversal, initial resistance + genuine update, lesson extracted | Compliant but passive, didn't explain why the new approach was better | Can't recall meaningful feedback — no growth signal |
| 80% → 90% accuracy | Error analysis → data vs. model distinction → cost-benefit on closing the gap | Right instincts, no structure, "experiment" without hypothesis | "Bigger model + more data" — no deployment thinking, no stopping condition |

---

## Closing Question

> *"If you joined our team, what's one thing about how we build AI at an enterprise that you'd want to understand in your first week?"*

**Strong answer:** Asks about data governance, model deployment pipeline, or how research connects to production.
**Weak answer:** Asks about which GPU cluster you use.

```

```