"""Blvckbot — primary conversational coordinator brain."""

from __future__ import annotations

import re
from typing import Any

from harness.core.agent_loop import AgentLoop
from harness.schemas.brain_info import BrainContext, BrainState
from harness.schemas.judgment import JudgmentEntry
from harness.schemas.message import HarnessMessage, MessageType
from harness.schemas.result import Result
from harness.schemas.task import Task
from judgment.lifecycle import JudgmentLifecycle, build_ledger_entry, result_status_for_outcome
from judgment.outcome import JudgmentOutcome
from judgment.profile import JudgmentProfile, ModelConfig

from brains._base.brain import BaseBrain

BLVCKBOT_SYSTEM_PROMPT = """You are Blvckbot, the primary intelligence of Blvckshell OS.

You are a conversational coordinator. You think before you act. You remember everything.

Your job:
- Understand what the operator wants, even when stated imprecisely
- Break goals into tasks and delegate to specialist brains
- Monitor what's happening and synthesize results into clear briefings
- Learn from every outcome — what worked, what failed, what was missed
- Ask clarifying questions when needed before acting
- Push back when something doesn't make sense

Your memory:
- Full conversation history with the operator
- All past judgments and their outcomes
- Accumulated doctrine — beliefs proven correct over time
- Durable notes from past conversations, recalled when relevant
- Standing opinions you've formed about the operator and the work — revise
  them explicitly when new evidence warrants it, rather than just adding more
- What each specialist brain has done and how well

How you operate:
- Think out loud when reasoning through a complex request
- State your plan before dispatching tasks
- Confirm before taking irreversible actions
- After results come back, always record what happened and what you learned
- Be direct. Don't hedge unnecessarily. You have context the operator doesn't need to re-explain.

When you recommend action, end with PROCEED.
When you need clarification, end with REQUEST_MORE_EVIDENCE and ask a direct question.
When you recommend caution, use STAGED_PROCEED or HOLD as appropriate.

You are not a chatbot. You are an organization's executive brain."""


class BlvckbotBrain(BaseBrain):
    """Conversational coordinator that delegates to specialist brains."""

    brain_id = "blvckbot"
    name = "Blvckbot"
    description = (
        "Primary interface brain. Coordinates specialist brains and maintains "
        "conversational context."
    )
    capabilities = ["coordinate", "converse", "plan", "synthesize", "delegate"]
    pipeline_participant = False
    judgment_profile = JudgmentProfile(
        domain="coordination",
        harm_guard_enabled=True,
        model=ModelConfig(
            preferred_model="claude-sonnet-4-6",
            fallback_models=["gpt-4o", "qwen2.5:72b"],
            temperature=0.7,
        ),
    )
    max_iterations = 4

    async def get_context(self, context_id: str, *, query: str | None = None) -> BrainContext:
        """Load working context plus recent judgments, doctrine, notes, and opinions."""
        return await self.runtime.memory.load_context(
            context_id, self.brain_id, judgment_limit=30, query=query
        )

    async def log_judgment(self, entry: JudgmentEntry) -> None:
        """Record a belief to the Judgment Ledger."""
        await self.runtime.memory.record_judgment(entry)

    async def handle_task(self, task: HarnessMessage) -> HarnessMessage:
        """Run the judgment lifecycle, delegate if appropriate, and respond."""
        parsed = Task.model_validate(task.payload)
        session_id = (
            task.metadata.get("session_id")
            or parsed.inputs.get("session_id")
            or await self.runtime.memory.conversations.get_or_create_session("operator")
        )
        context = await self.get_context(task.context_id, query=parsed.objective)
        history = await self.runtime.memory.conversations.get_history(session_id, limit=50)
        registry_brains = await self.runtime.registry.list_all()

        await self.set_state(BrainState.THINKING)
        user_prompt = self._build_prompt(parsed, history, context, registry_brains)

        loop = AgentLoop(
            llm=self.runtime.llm,
            tools=self.tools,
            observer=self.runtime.observer,
            max_iterations=self.max_iterations,
            model_config=self.judgment_profile.model,
            settings=self.runtime.settings,
        )

        async def gather_evidence():
            legacy_model = (
                None
                if self.judgment_profile.model
                else (self.model if self.model != "fake-llm" else None)
            )
            return await loop.run(
                brain_id=self.brain_id,
                context_id=task.context_id,
                system_prompt=BLVCKBOT_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                model=legacy_model,
            )

        lifecycle = JudgmentLifecycle()
        cycle = await lifecycle.run(
            brain_id=self.brain_id,
            context_id=task.context_id,
            task=parsed,
            context=context,
            profile=self.judgment_profile,
            gather_evidence=gather_evidence,
            observer=self.runtime.observer,
        )

        actions_taken: list[dict[str, Any]] = []
        agent_summaries: list[str] = []

        if cycle.outcome in (JudgmentOutcome.PROCEED, JudgmentOutcome.STAGED_PROCEED):
            await self.set_state(BrainState.EXECUTING)
            delegations = self._plan_delegations(parsed.objective, registry_brains, cycle.outcome)
            for capability, objective in delegations:
                call = await self.spawn_agent(
                    capability=capability,
                    objective=objective,
                    parent_task_id=parsed.id,
                    run_id=parsed.run_id,
                    objective_id=parsed.objective_id,
                    timeout=90.0,
                )
                action = {
                    "capability": capability,
                    "brain_id": call.target_brain_id,
                    "objective": objective[:160],
                    "status": call.status.value,
                    "result": (call.result or "")[:280],
                }
                actions_taken.append(action)
                if call.result:
                    agent_summaries.append(f"[{capability}] {call.result[:200]}")

        response_text = self._synthesize_response(
            cycle.raw_analysis,
            cycle.outcome,
            agent_summaries,
        )

        judgment = build_ledger_entry(
            brain_id=self.brain_id,
            context_id=task.context_id,
            lifecycle=cycle,
        )
        judgment.belief = response_text[:500]
        await self.log_judgment(judgment)

        await self.runtime.memory.conversations.append(
            session_id,
            "blvckbot",
            response_text,
            metadata={
                "judgment_outcome": cycle.outcome.value,
                "judgment_id": judgment.id,
                "actions_taken": actions_taken,
            },
            brain_id=self.brain_id,
        )

        result = Result(
            task_id=parsed.id,
            brain_id=self.brain_id,
            status=result_status_for_outcome(cycle.outcome),
            output={
                "analysis": cycle.raw_analysis,
                "judgment_outcome": cycle.outcome.value,
                "actions_taken": actions_taken,
                "session_id": session_id,
                "response": response_text,
            },
            summary=response_text[:280],
            judgment_ids=[judgment.id],
            judgment_outcome=cycle.outcome,
            stage_trace_id=cycle.trace_id,
            metrics=cycle.agent_metrics,
        )
        await self.runtime.memory.append_working(
            task.context_id,
            "history",
            {
                "brain": self.brain_id,
                "summary": result.summary,
                "session_id": session_id,
            },
        )
        return task.reply(
            source=self.brain_id,
            message_type=MessageType.RESULT,
            payload=result.model_dump(mode="json"),
            metadata={"session_id": session_id, **cycle.agent_metrics},
        )

    def _build_prompt(
        self,
        task: Task,
        history,
        context: BrainContext,
        registry_brains,
    ) -> str:
        """Render operator message with conversation and registry context."""
        transcript = "\n".join(
            f"{entry.role.upper()}: {entry.content[:400]}" for entry in history[-20:]
        ) or "(no prior messages)"
        capabilities = "\n".join(
            f"- {brain.brain_id}: {brain.capabilities} — {brain.description}"
            for brain in registry_brains
            if brain.brain_id != self.brain_id
        ) or "- (no specialists registered)"
        doctrine = "\n".join(f"- {d.belief[:120]}" for d in context.doctrine[:5]) or "- (none)"
        judgments = (
            "\n".join(
                f"- [{j.brain_id}] {j.belief[:100]} (confidence={j.confidence})"
                for j in context.recent_judgments[-5:]
            )
            or "- (none)"
        )
        attachment_block = self._format_attachments(task.inputs.get("attachments") or [])
        notes = "\n".join(f"- {n.content[:160]}" for n in context.notes[:5]) or "- (none)"
        opinions = (
            "\n".join(
                f"- [{o.topic}] {o.statement[:160]} (confidence={o.confidence})"
                for o in context.opinions[:5]
            )
            or "- (none)"
        )
        return (
            f"OPERATOR REQUEST:\n{task.objective}\n\n"
            f"{attachment_block}"
            f"CONVERSATION HISTORY:\n{transcript}\n\n"
            f"AVAILABLE SPECIALIST BRAINS:\n{capabilities}\n\n"
            f"RECENT JUDGMENTS:\n{judgments}\n\n"
            f"DOCTRINE:\n{doctrine}\n\n"
            f"MEMORY NOTES:\n{notes}\n\n"
            f"STANDING OPINIONS:\n{opinions}\n\n"
            "Reason through the request. State your plan. Recommend PROCEED, "
            "STAGED_PROCEED, REQUEST_MORE_EVIDENCE, or HOLD explicitly."
        )

    @staticmethod
    def _format_attachments(attachments: list) -> str:
        """Render attached files for the evidence-gathering prompt."""
        if not attachments:
            return ""
        import base64

        lines = ["ATTACHMENTS:"]
        for item in attachments:
            if not isinstance(item, dict):
                continue
            filename = item.get("filename", "file")
            media_type = item.get("media_type", "application/octet-stream")
            kind = item.get("type", "document")
            lines.append(f"- {filename} ({kind}, {media_type})")
            if kind == "document" and media_type.startswith("text/"):
                try:
                    raw = base64.b64decode(item.get("data", ""))
                    text = raw.decode("utf-8", errors="replace")[:4000]
                    lines.append(f"  content preview:\n{text}")
                except Exception:
                    lines.append("  (could not decode text content)")
            elif kind == "image":
                lines.append("  (image data provided — describe and reason about it)")
        lines.append("")
        return "\n".join(lines) + "\n"

    def _plan_delegations(
        self,
        message: str,
        registry_brains,
        outcome: JudgmentOutcome,
    ) -> list[tuple[str, str]]:
        """Select capabilities to delegate based on registry and message keywords."""
        lower = message.lower()
        selected: list[tuple[str, str]] = []
        seen_capabilities: set[str] = set()

        keyword_map = [
            (("build", "idea", "market", "validate", "startup", "venture"), "venture", None),
            (("capital", "fund", "finance", "budget", "invest", "money"), "capital", None),
            (("plan", "execute", "milestone", "launch", "roadmap"), "commander", None),
            (
                ("research", "look up", "verify", "fact check", "source", "evidence",
                 "is it true", "how much does", "what does it cost", "competitor"),
                "research",
                "evidence_research",
            ),
        ]

        for brain in registry_brains:
            if brain.brain_id in (self.brain_id, "blvckbot"):
                continue
            for keywords, brain_id, capability in keyword_map:
                if brain.brain_id != brain_id or not any(word in lower for word in keywords):
                    continue
                chosen = capability if capability in brain.capabilities else (
                    brain.capabilities[0] if brain.capabilities else None
                )
                if chosen is None or chosen in seen_capabilities:
                    continue
                seen_capabilities.add(chosen)
                objective = f"Support Blvckbot on: {message[:300]}"
                selected.append((chosen, objective))

        if not selected and outcome == JudgmentOutcome.PROCEED:
            for brain in registry_brains:
                if brain.brain_id == self.brain_id or not brain.capabilities:
                    continue
                capability = brain.capabilities[0]
                if capability not in seen_capabilities:
                    selected.append((capability, f"Review and advise on: {message[:300]}"))
                    if len(selected) >= 2:
                        break

        if outcome == JudgmentOutcome.STAGED_PROCEED:
            return selected[:1]
        return selected[:3]

    def _synthesize_response(
        self,
        analysis: str,
        outcome: JudgmentOutcome,
        agent_summaries: list[str],
    ) -> str:
        """Combine Blvckbot reasoning with specialist results."""
        if outcome == JudgmentOutcome.REQUEST_MORE_EVIDENCE:
            question = self._extract_question(analysis)
            return (
                question
                or "I need more detail before I can act. What outcome are you optimizing for?"
            )

        if outcome == JudgmentOutcome.HOLD:
            return f"I'm holding on this for now. {analysis[:400]}"

        if agent_summaries:
            joined = "\n".join(agent_summaries)
            return f"{analysis[:400]}\n\nSpecialist input:\n{joined}"[:1200]

        return analysis[:800]

    @staticmethod
    def _extract_question(text: str) -> str | None:
        """Pull the first question mark sentence from model output."""
        match = re.search(r"([^.?\n]{10,}\?)", text)
        return match.group(1).strip() if match else None
