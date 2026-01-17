"""
LLM Context Manager V2 - Optimized with Response ID Branching

Key insight: response_id supports branching! Instead of using a separate
summarization model that must re-read all messages, we can:

1. Save response_ids at checkpoints during conversation
2. Branch from a checkpoint to generate summaries
3. The summary call reuses cached KV attention - MUCH faster!

This eliminates the need for a separate summary_model entirely.
"""

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from dotenv import load_dotenv
from enum import StrEnum
from pydantic import BaseModel, Field, ConfigDict
from openai import OpenAI

load_dotenv()

# dedicated logger
summary_logger = logging.getLogger("llm_context_manager_v2")
summary_logger.setLevel(logging.DEBUG)

if not summary_logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    )
    summary_logger.addHandler(console_handler)


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    role: MessageRole = Field(description="The role of the message sender")
    content: str = Field(description="The content of the message")


class Checkpoint(BaseModel):
    """A saved point in the conversation we can branch from."""
    response_id: str = Field(description="The response_id at this checkpoint")
    message_idx: int = Field(description="Index of the last message at this checkpoint")
    char_count: int = Field(description="Total chars in context at this checkpoint")


class Summary(BaseModel):
    summary: str = Field(description="The summary of the conversation")
    anchor_message_idx: int = Field(description="The anchor idx of the conversation")


class LLMContextManagerV2(BaseModel):
    """
    Optimized LLM Context Manager using response_id branching for summarization.

    Key difference from V1: No separate summary model!
    We branch from saved checkpoints to generate summaries using cached context.
    """

    # single model for everything
    model: str = Field(default="gpt-5.1", description="The model to use")

    # context window hyper parameters
    T_max: int = Field(default=50_000, description="Maximum chars before forced drain")
    T_drain: int = Field(default=30_000, description="Threshold to start async summarization")
    T_target: int = Field(default=18_000, description="Target chars after drain")
    T_summary_max: int = Field(default=10_000, description="Maximum chars for summary")
    max_message_size: int = Field(default=300_000, description="Maximum chars per single message")

    # checkpoint frequency - save a checkpoint every N chars of new content
    checkpoint_interval: int = Field(default=10_000, description="Save checkpoint every N chars")

    # session state
    client: OpenAI = Field(default_factory=lambda: OpenAI(api_key=os.getenv("OPENAI_API_KEY")))
    T_current: int = Field(default=0, description="Current chars in context window")
    messages: list[Message] = Field(default_factory=list, description="All messages in conversation")
    summaries: list[Summary] = Field(default_factory=list, description="Summaries at various anchor points")
    current_anchor_idx: int | None = Field(default=None, description="Current anchor message index")

    # response_id tracking - THIS IS THE KEY DIFFERENCE
    last_response_id: str | None = Field(default=None, description="Last response id for main continuation")
    checkpoints: list[Checkpoint] = Field(default_factory=list, description="Saved checkpoints for branching")
    chars_since_checkpoint: int = Field(default=0, description="Chars added since last checkpoint")

    # async summarization state
    summarization_in_progress: bool = False
    draining: bool = False
    summarization_done: threading.Event = Field(default_factory=threading.Event)
    summarization_lock: threading.Lock = Field(default_factory=threading.Lock)
    executor: ThreadPoolExecutor = Field(default_factory=lambda: ThreadPoolExecutor(max_workers=1))

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def start_session(self, system_prompt: str) -> None:
        """Initialize a new session with a system prompt."""
        if len(system_prompt) > self.T_target // 2:
            raise ValueError("System prompt too long")

        self.messages = [Message(role=MessageRole.SYSTEM, content=system_prompt)]
        self.T_current = len(system_prompt)
        self.summaries = []
        self.checkpoints = []
        self.current_anchor_idx = None
        self.last_response_id = None
        self.chars_since_checkpoint = 0

        summary_logger.info(
            f"[SESSION] Started | system={len(system_prompt):,} chars | "
            f"T_drain={self.T_drain:,} | T_max={self.T_max:,}"
        )

    def _save_checkpoint(self) -> None:
        """Save current response_id as a checkpoint for future branching."""
        if self.last_response_id is None:
            return

        checkpoint = Checkpoint(
            response_id=self.last_response_id,
            message_idx=len(self.messages) - 1,
            char_count=self.T_current
        )
        self.checkpoints.append(checkpoint)
        self.chars_since_checkpoint = 0

        summary_logger.info(
            f"[CHECKPOINT] Saved | idx={checkpoint.message_idx} | "
            f"chars={checkpoint.char_count:,} | total_checkpoints={len(self.checkpoints)}"
        )

    def _maybe_save_checkpoint(self, new_chars: int) -> None:
        """Save a checkpoint if we've accumulated enough new content."""
        self.chars_since_checkpoint += new_chars

        if self.chars_since_checkpoint >= self.checkpoint_interval:
            self._save_checkpoint()

    def get_response(self, user_message: str) -> str:
        """Get a response from the LLM for the user message."""
        if len(user_message) > self.max_message_size:
            raise ValueError(f"Message too large: {len(user_message):,} chars")

        # add user message
        self.messages.append(Message(role=MessageRole.USER, content=user_message))
        self.T_current += len(user_message)

        # check if we need to drain BEFORE calling LLM
        if self.T_current > self.T_max:
            self._drain_context()

        # build input and call LLM
        llm_input = self._build_llm_input()

        if self.last_response_id is not None:
            response = self.client.responses.create(
                model=self.model,
                previous_response_id=self.last_response_id,
                input=llm_input
            )
        else:
            response = self.client.responses.create(
                model=self.model,
                input=llm_input
            )

        assistant_content = response.output_text
        self.last_response_id = response.id

        # add assistant message
        self.messages.append(Message(role=MessageRole.ASSISTANT, content=assistant_content))
        self.T_current += len(assistant_content)

        # maybe save checkpoint (based on accumulated chars)
        self._maybe_save_checkpoint(len(user_message) + len(assistant_content))

        # check if we need to start async summarization
        if self.T_current > self.T_drain:
            self._maybe_start_async_summarization()

        return assistant_content

    def _build_llm_input(self) -> list[dict]:
        """Build the input messages for the LLM based on current state."""
        # continuation mode - just send new message
        if self.last_response_id is not None:
            return [{"role": self.messages[-1].role.value, "content": self.messages[-1].content}]

        # fresh session - send all messages
        if self.current_anchor_idx is None:
            return [{"role": m.role.value, "content": m.content} for m in self.messages]

        # post-drain: system + summary + messages after anchor
        input_messages = []

        # system prompt
        input_messages.append({"role": "system", "content": self.messages[0].content})

        # summary context
        summary_text = self._get_summary_for_anchor(self.current_anchor_idx)
        if summary_text:
            summary_context = (
                f"<conversation_summary>\n{summary_text}\n</conversation_summary>\n\n"
                "Continue naturally without explicitly referencing this summary."
            )
            input_messages.append({"role": "system", "content": summary_context})

        # messages after anchor
        for msg in self.messages[self.current_anchor_idx + 1:]:
            input_messages.append({"role": msg.role.value, "content": msg.content})

        return input_messages

    def _maybe_start_async_summarization(self) -> None:
        """Start async summarization using BRANCHING from a checkpoint."""
        with self.summarization_lock:
            if self.summarization_in_progress or self.draining:
                return
            if not self.checkpoints:
                summary_logger.warning("[SUMMARIZE] No checkpoints available for branching")
                return
            self.summarization_in_progress = True
            self.summarization_done.clear()

        summary_logger.info("[SUMMARIZE] Starting async summarization via BRANCHING...")
        self.executor.submit(self._async_summarization_worker)

    def _async_summarization_worker(self) -> None:
        """Background worker - generates summary by BRANCHING from checkpoint."""
        import time
        start_time = time.time()

        try:
            self._generate_summary_via_branch()
            elapsed = time.time() - start_time
            summary_logger.info(f"[SUMMARIZE] Completed in {elapsed:.1f}s")
        except Exception as e:
            summary_logger.error(f"[SUMMARIZE] Failed: {e}", exc_info=True)
        finally:
            with self.summarization_lock:
                self.summarization_in_progress = False
            self.summarization_done.set()

    def _generate_summary_via_branch(self) -> None:
        """
        THE KEY OPTIMIZATION: Generate summary by branching from a checkpoint.

        Instead of calling a separate model that re-reads everything,
        we branch from a saved response_id. The model already has the
        context cached - we just ask it to summarize!
        """
        if not self.checkpoints:
            summary_logger.warning("[SUMMARY-GEN] No checkpoints to branch from")
            return

        # use the most recent checkpoint
        checkpoint = self.checkpoints[-1]

        summary_logger.info(
            f"[SUMMARY-GEN] Branching from checkpoint | "
            f"msg_idx={checkpoint.message_idx} | chars={checkpoint.char_count:,}"
        )

        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # build the summary request - this branches from the checkpoint!
        summary_prompt = self._get_summary_prompt(current_timestamp)

        # BRANCH from the checkpoint's response_id
        # This reuses the cached KV attention - no re-encoding needed!
        response = self.client.responses.create(
            model=self.model,
            previous_response_id=checkpoint.response_id,  # ← BRANCH HERE!
            input=[{"role": "user", "content": summary_prompt}]
        )

        summary_text = response.output_text
        summary_logger.info(f"[SUMMARY-GEN] Got {len(summary_text):,} chars from branch")

        # Shrink if needed - IMPORTANT: continue on the SUMMARY branch, not main!
        # This keeps the shrink chain isolated: checkpoint → summary → shrink1 → shrink2
        # The main conversation's self.last_response_id is NEVER touched here.
        current_response_id = response.id  # summary's response_id (not main!)
        shrink_attempts = 0

        while len(summary_text) > self.T_summary_max and shrink_attempts < 3:
            shrink_attempts += 1
            summary_logger.info(f"[SUMMARY-GEN] Shrinking (attempt {shrink_attempts})")

            shrink_response = self.client.responses.create(
                model=self.model,
                previous_response_id=current_response_id,  # continue the branch
                input=[{
                    "role": "user",
                    "content": f"That's {len(summary_text):,} chars but must be under {self.T_summary_max:,}. Compress it. Output ONLY the shorter summary."
                }]
            )

            new_text = shrink_response.output_text
            if len(new_text) >= len(summary_text):
                # hard truncate
                summary_text = summary_text[:self.T_summary_max - 100] + "\n[...truncated...]"
                break
            summary_text = new_text
            current_response_id = shrink_response.id

        # store the summary
        self._upsert_summary(checkpoint.message_idx, summary_text)
        summary_logger.info(
            f"[SUMMARY-GEN] Stored | anchor={checkpoint.message_idx} | size={len(summary_text):,}"
        )

    def _get_summary_prompt(self, timestamp: str) -> str:
        """Generate the prompt asking the model to summarize the conversation so far."""
        previous_summary = self._get_summary_for_anchor(len(self.messages) - 1)

        if previous_summary:
            return f"""Please update this Session Memory based on our conversation:

{previous_summary}

---
Create an updated summary capturing:
- User objectives and preferences
- Technical context (paths, functions, values - preserve exactly)
- Decisions made
- Active tasks and open questions

Use timestamp [{timestamp}] for new/updated items.
Target: {self.T_summary_max} chars max.
Output ONLY the Session Memory markdown."""
        else:
            return f"""Please create a Session Memory summarizing our conversation so far.

Capture:
- User objectives and preferences
- Technical context (paths, functions, values - preserve exactly)
- Decisions made
- Active tasks and open questions

Use timestamp [{timestamp}] for all items.
Target: {self.T_summary_max} chars max.
Output ONLY the Session Memory markdown."""

    def _drain_context(self) -> None:
        """Drain context when T_current > T_max."""
        pre_drain_size = self.T_current
        summary_logger.warning(f"[DRAIN] Starting | T_current={self.T_current:,} > T_max={self.T_max:,}")

        with self.summarization_lock:
            self.draining = True
            was_in_progress = self.summarization_in_progress

        if was_in_progress:
            summary_logger.info("[DRAIN] Waiting for in-progress summarization...")
            self.summarization_done.wait(timeout=30)

        try:
            # ensure we have a summary before draining
            if not self.summaries and self.checkpoints:
                self._generate_summary_via_branch()

            # calculate new anchor
            new_anchor_idx, overhead, accumulated = self._calculate_drain_anchor()

            self.current_anchor_idx = new_anchor_idx
            self.last_response_id = None  # force fresh context

            # clear old checkpoints (before the anchor)
            self.checkpoints = [cp for cp in self.checkpoints if cp.message_idx > new_anchor_idx]

            # mark drained messages
            for i in range(1, self.current_anchor_idx + 1):
                self.messages[i] = Message(role=self.messages[i].role, content="[deleted]")

            self.T_current = overhead + accumulated

            summary_logger.warning(
                f"[DRAIN] Complete | {pre_drain_size:,} → {self.T_current:,} chars | "
                f"anchor={new_anchor_idx} | remaining_checkpoints={len(self.checkpoints)}"
            )

        finally:
            with self.summarization_lock:
                self.draining = False

    def _calculate_drain_anchor(self) -> tuple[int, int, int]:
        """Calculate where to set the anchor during drain."""
        system_prompt_size = len(self.messages[0].content)
        summary_size = len(self._get_summary_for_anchor(len(self.messages) - 1) or "")
        overhead = system_prompt_size + summary_size + 500

        available = self.T_target - overhead
        accumulated = 0
        new_anchor_idx = len(self.messages) - 1

        for i in range(len(self.messages) - 1, 0, -1):
            msg_size = len(self.messages[i].content)
            if accumulated + msg_size > available:
                new_anchor_idx = i
                break
            accumulated += msg_size
            new_anchor_idx = i - 1

        return max(new_anchor_idx, 1), overhead, accumulated

    def _upsert_summary(self, anchor_idx: int, summary_text: str) -> None:
        """Insert or update a summary."""
        for i, s in enumerate(self.summaries):
            if s.anchor_message_idx == anchor_idx:
                self.summaries[i] = Summary(summary=summary_text, anchor_message_idx=anchor_idx)
                return
        self.summaries.append(Summary(summary=summary_text, anchor_message_idx=anchor_idx))

    def _get_summary_for_anchor(self, anchor_idx: int) -> str | None:
        """Get the best summary for a given anchor point."""
        if not self.summaries:
            return None
        best = None
        for summary in self.summaries:
            if summary.anchor_message_idx <= anchor_idx:
                best = summary.summary
        return best

    def get_stats(self) -> dict:
        """Get current stats."""
        return {
            "T_current": self.T_current,
            "T_drain": self.T_drain,
            "T_max": self.T_max,
            "T_target": self.T_target,
            "T_summary_max": self.T_summary_max,
            "message_count": len(self.messages),
            "summary_count": len(self.summaries),
            "checkpoint_count": len(self.checkpoints),
            "current_anchor_idx": self.current_anchor_idx,
            "has_response_id": self.last_response_id is not None,
            "summarization_in_progress": self.summarization_in_progress,
        }
