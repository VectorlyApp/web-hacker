"""
LLM Context Manager V3 - Simplified with Lazy Summarization

Key insight: Since branching reuses KV cache and is FAST, we don't need
async summarization at all! Just summarize on-demand at drain time.

Strategy:
1. Save checkpoints periodically (just response_ids - very cheap)
2. When T_current > T_max, branch from checkpoint to summarize
3. Summarization is fast because context is already cached
4. No wasted API calls, summary is always fresh
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from enum import StrEnum
from pydantic import BaseModel, Field, ConfigDict
from openai import OpenAI

load_dotenv()

summary_logger = logging.getLogger("llm_context_manager_v3")
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
    role: MessageRole
    content: str


class Checkpoint(BaseModel):
    """A saved point we can branch from for summarization."""
    response_id: str
    message_idx: int
    token_count: int  # Context size in tokens at this checkpoint


class LLMContextManagerV3(BaseModel):
    """
    Simplified LLM Context Manager with lazy summarization.

    No async summarization - just branch and summarize at drain time.
    This is efficient because branching reuses the KV cache!
    """

    model: str = Field(default="gpt-5.1")

    # Thresholds - NOW IN TOKENS!
    T_max: int = Field(default=8_000, description="Drain when exceeded (tokens)")
    T_target: int = Field(default=4_000, description="Target after drain (tokens)")
    T_summary_max: int = Field(default=2_000, description="Max summary size (tokens)")
    max_message_size: int = Field(default=100_000, description="Max message size (chars)")

    # Checkpoint frequency (in tokens)
    checkpoint_interval: int = Field(default=2_000, description="Save checkpoint every N tokens")

    # Optional: dump summaries to disk for debugging
    summaries_dir: Path | None = Field(default=None, description="Directory to save summaries")

    # State
    client: OpenAI = Field(default_factory=lambda: OpenAI(api_key=os.getenv("OPENAI_API_KEY")))
    messages: list[Message] = Field(default_factory=list)
    last_response_id: str | None = Field(default=None)

    # Context size tracking - PRIMARY is tokens, chars for fallback/debugging
    T_current_tokens: int = Field(default=0, description="Current context size in tokens")
    T_current_chars: int = Field(default=0, description="Current context size in chars (for reference)")
    tokens_calibrated: bool = Field(default=False, description="True after first API call gives us real token counts")

    # Checkpoints for branching
    checkpoints: list[Checkpoint] = Field(default_factory=list)
    tokens_since_checkpoint: int = Field(default=0)

    # Summary (only one needed - generated fresh at drain)
    current_summary: str | None = Field(default=None)
    summary_anchor_idx: int | None = Field(default=None)
    current_anchor_idx: int | None = Field(default=None)

    # Token usage tracking
    total_input_tokens: int = Field(default=0)
    total_output_tokens: int = Field(default=0)
    total_cached_tokens: int = Field(default=0)
    api_call_count: int = Field(default=0)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def start_session(self, system_prompt: str) -> None:
        """Initialize a new session."""
        self.messages = [Message(role=MessageRole.SYSTEM, content=system_prompt)]

        # Track chars (always accurate) and estimate tokens until calibrated
        self.T_current_chars = len(system_prompt)
        self.T_current_tokens = self._estimate_tokens(system_prompt)
        self.tokens_calibrated = False

        self.checkpoints = []
        self.current_summary = None
        self.summary_anchor_idx = None
        self.current_anchor_idx = None
        self.last_response_id = None
        self.tokens_since_checkpoint = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cached_tokens = 0
        self.api_call_count = 0

        summary_logger.info(f"[SESSION] Started | T_max={self.T_max:,} tokens | T_target={self.T_target:,} tokens")

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from text. ~4 chars per token for English."""
        return len(text) // 4

    def _get_effective_tokens(self) -> int:
        """Get current token count - actual if calibrated, estimated if not."""
        if self.tokens_calibrated:
            return self.T_current_tokens
        return self._estimate_tokens_from_chars(self.T_current_chars)

    def _estimate_tokens_from_chars(self, chars: int) -> int:
        """Estimate tokens from character count."""
        return chars // 4

    def _track_token_usage(self, response, call_type: str = "chat", is_fresh_context: bool = False) -> None:
        """
        Track and log token usage from an API response.

        Updates T_current_tokens based on the response:
        - On FRESH context: input_tokens IS our current context size (before output)
        - On CONTINUATION: add input_tokens + output_tokens to running total
        - After any call: add output_tokens to context

        Args:
            response: The API response object
            call_type: Type of call for logging ("chat", "summary", "shrink")
            is_fresh_context: True if this was a fresh context call (not continuation)
        """
        self.api_call_count += 1

        if not hasattr(response, 'usage') or response.usage is None:
            summary_logger.warning(f"[TOKENS] No usage data in response")
            return

        usage = response.usage
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens

        # Track cumulative totals (for billing/stats)
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        # Check for OpenAI's prompt caching
        cached_tokens = 0
        if hasattr(usage, 'input_tokens_details') and usage.input_tokens_details:
            cached_tokens = getattr(usage.input_tokens_details, 'cached_tokens', 0) or 0
        self.total_cached_tokens += cached_tokens

        # Update T_current_tokens (the actual context window size)
        if is_fresh_context:
            # Fresh context: input_tokens = full context we sent
            # Now add output_tokens for the response
            self.T_current_tokens = input_tokens + output_tokens
            self.tokens_calibrated = True
            summary_logger.info(
                f"[TOKENS] {call_type} [FRESH] | in={input_tokens:,} out={output_tokens:,} "
                f"| T_current={self.T_current_tokens:,} tokens (CALIBRATED)"
            )
        else:
            # Continuation: KV cache has previous context, we only sent new message
            # Context grows by input_tokens (new msg) + output_tokens (response)
            self.T_current_tokens += input_tokens + output_tokens
            summary_logger.info(
                f"[TOKENS] {call_type} [CONT] | +in={input_tokens:,} +out={output_tokens:,} "
                f"| T_current={self.T_current_tokens:,} tokens"
            )

    def get_response(self, user_message: str) -> str:
        """Get a response from the LLM."""
        if len(user_message) > self.max_message_size:
            raise ValueError(f"Message too large: {len(user_message):,} chars")

        self.messages.append(Message(role=MessageRole.USER, content=user_message))
        self.T_current_chars += len(user_message)

        # Estimate tokens for new message (will be corrected after API call)
        if not self.tokens_calibrated:
            self.T_current_tokens += self._estimate_tokens(user_message)

        # Check drain BEFORE calling LLM (use effective token count)
        effective_tokens = self._get_effective_tokens()
        if effective_tokens > self.T_max:
            self._drain_context()

        # Call LLM - track if this is fresh or continuation
        llm_input = self._build_llm_input()
        is_fresh = self.last_response_id is None

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

        # Track tokens - this calibrates T_current_tokens!
        self._track_token_usage(response, "chat", is_fresh_context=is_fresh)

        assistant_content = response.output_text
        self.last_response_id = response.id

        self.messages.append(Message(role=MessageRole.ASSISTANT, content=assistant_content))
        self.T_current_chars += len(assistant_content)

        # Save checkpoint if enough new tokens (estimate based on chars for this turn)
        turn_tokens = self._estimate_tokens(user_message + assistant_content)
        self._maybe_save_checkpoint(turn_tokens)

        return assistant_content

    def _save_checkpoint(self) -> None:
        """Save current response_id as a checkpoint.

        The checkpoint's message_idx is the LAST ASSISTANT message,
        since that's what generated the response_id.
        """
        if self.last_response_id is None:
            return

        # Find the last assistant message - that's what the response_id corresponds to
        last_assistant_idx = None
        for i in range(len(self.messages) - 1, -1, -1):
            if self.messages[i].role == MessageRole.ASSISTANT:
                last_assistant_idx = i
                break

        if last_assistant_idx is None:
            summary_logger.warning("[CHECKPOINT] No assistant message found - cannot save checkpoint")
            return

        self.checkpoints.append(Checkpoint(
            response_id=self.last_response_id,
            message_idx=last_assistant_idx,
            token_count=self.T_current_tokens
        ))
        self.tokens_since_checkpoint = 0
        summary_logger.info(f"[CHECKPOINT] Saved @ msg {last_assistant_idx} | {self.T_current_tokens:,} tokens | total={len(self.checkpoints)}")

    def _maybe_save_checkpoint(self, new_tokens: int) -> None:
        """Save checkpoint if accumulated enough tokens."""
        self.tokens_since_checkpoint += new_tokens
        if self.tokens_since_checkpoint >= self.checkpoint_interval:
            self._save_checkpoint()

    def _build_llm_input(self) -> list[dict]:
        """Build input for LLM."""
        # Continuation mode
        if self.last_response_id is not None:
            return [{"role": self.messages[-1].role.value, "content": self.messages[-1].content}]

        # Fresh session
        if self.current_anchor_idx is None:
            return [{"role": m.role.value, "content": m.content} for m in self.messages]

        # Post-drain: system + summary + recent messages
        input_messages = [{"role": "system", "content": self.messages[0].content}]

        if self.current_summary:
            input_messages.append({
                "role": "system",
                "content": f"<conversation_summary>\n{self.current_summary}\n</conversation_summary>\n\nContinue naturally."
            })

        for msg in self.messages[self.current_anchor_idx + 1:]:
            input_messages.append({"role": msg.role.value, "content": msg.content})

        return input_messages

    def force_drain(self) -> None:
        """Public method to force a context drain regardless of current size."""
        self._drain_context()

    def _drain_context(self) -> None:
        """Drain context - generate summary via branching, then truncate."""
        pre_drain_tokens = self.T_current_tokens
        pre_drain_chars = self.T_current_chars
        summary_logger.warning(f"[DRAIN] Starting | T_current={self.T_current_tokens:,} tokens > T_max={self.T_max:,}")

        # Step 1: Calculate what to keep FIRST (need this to choose optimal checkpoint)
        new_anchor_idx, overhead_tokens, accumulated_tokens = self._calculate_drain_anchor()
        summary_logger.info(f"[DRAIN] Will delete msgs 1-{new_anchor_idx}, keep {new_anchor_idx+1}-{len(self.messages)-1}")

        # Step 2: Find OPTIMAL checkpoint to branch from for summary
        # We want a checkpoint that has seen the content we're deleting
        optimal_checkpoint = self._find_optimal_checkpoint_for_summary(new_anchor_idx)

        if optimal_checkpoint:
            self._generate_summary_via_branch(optimal_checkpoint, new_anchor_idx)
        else:
            summary_logger.warning("[DRAIN] No suitable checkpoint - cannot generate summary")

        # Step 3: Update state
        self.current_anchor_idx = new_anchor_idx
        self.last_response_id = None  # Force fresh context

        # Clear old checkpoints
        self.checkpoints = [cp for cp in self.checkpoints if cp.message_idx > new_anchor_idx]

        # Mark old messages as deleted and recalculate chars
        deleted_chars = 0
        for i in range(1, self.current_anchor_idx + 1):
            deleted_chars += len(self.messages[i].content)
            self.messages[i] = Message(role=self.messages[i].role, content="[deleted]")

        # Update tracking - tokens will be recalibrated on next fresh API call
        self.T_current_tokens = overhead_tokens + accumulated_tokens
        self.T_current_chars = pre_drain_chars - deleted_chars + (len(self.current_summary) if self.current_summary else 0)
        self.tokens_calibrated = False  # Need recalibration after drain

        summary_logger.warning(f"[DRAIN] Complete | {pre_drain_tokens:,} → {self.T_current_tokens:,} tokens (estimated)")

    def _find_optimal_checkpoint_for_summary(self, anchor_idx: int) -> Checkpoint | None:
        """
        Find the best checkpoint to branch from for summarization.

        Strategy: Find the checkpoint closest to (but not after) the anchor.
        This checkpoint has seen the most content that we're about to delete.

        Example:
            Messages: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
            Checkpoints at: msg 2, msg 5, msg 8
            Anchor: 7 (delete 1-7, keep 8-10)

            → Best checkpoint: msg 5 (closest to anchor, has seen 1-5)
            → NOT msg 8 (after anchor, hasn't seen full deleted content)
        """
        if not self.checkpoints:
            return None

        # Find checkpoints AT or BEFORE the anchor
        valid_checkpoints = [cp for cp in self.checkpoints if cp.message_idx <= anchor_idx]

        if not valid_checkpoints:
            # All checkpoints are after anchor - use the earliest one
            # (it still has SOME context, better than nothing)
            summary_logger.warning(
                f"[CHECKPOINT] No checkpoints before anchor {anchor_idx}, "
                f"using earliest checkpoint at {self.checkpoints[0].message_idx}"
            )
            return self.checkpoints[0]

        # Return the one closest to anchor (has seen the most content)
        best = max(valid_checkpoints, key=lambda cp: cp.message_idx)
        summary_logger.info(
            f"[CHECKPOINT] Selected checkpoint @ msg {best.message_idx} "
            f"(anchor={anchor_idx}, covers msgs 1-{best.message_idx})"
        )
        return best

    def _generate_summary_via_branch(self, checkpoint: Checkpoint, anchor_idx: int) -> None:
        """Generate summary by branching from checkpoint - FAST because KV is cached!"""
        summary_logger.info(f"[SUMMARY] Branching from checkpoint @ msg {checkpoint.message_idx}")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Branch from checkpoint to generate summary
        # The checkpoint is at msg X, anchor is at msg Y where Y >= X
        # KV cache has msgs 1-X. We need to include X+1 to anchor in the request.

        # Build input: include any messages between checkpoint and anchor
        summary_input = []

        # Add messages the checkpoint HASN'T seen (X+1 to anchor)
        gap_messages = self.messages[checkpoint.message_idx + 1 : anchor_idx + 1]
        if gap_messages:
            summary_logger.info(f"[SUMMARY] Adding {len(gap_messages)} gap messages to request")
            for msg in gap_messages:
                if msg.content != "[deleted]":
                    summary_input.append({"role": msg.role.value, "content": msg.content})

        # Final instruction to summarize
        summary_input.append({
            "role": "user",
            "content": f"""Now summarize our ENTIRE conversation (everything discussed so far).

Create a concise Session Memory document with:
- User's objectives and preferences
- Technical context (paths, functions, values - preserve EXACTLY)
- Key decisions made
- Active tasks and open questions

Use timestamp [{timestamp}]. Target: {self.T_summary_max} chars max.
Output ONLY the summary markdown, no preamble."""
        })

        response = self.client.responses.create(
            model=self.model,
            previous_response_id=checkpoint.response_id,
            input=summary_input
        )

        self._track_token_usage(response, "summary")
        summary_text = response.output_text
        summary_logger.info(f"[SUMMARY] Got {len(summary_text):,} chars")

        # Shrink if needed (continue on summary branch)
        branch_id = response.id
        while len(summary_text) > self.T_summary_max:
            summary_logger.info(f"[SUMMARY] Shrinking ({len(summary_text):,} > {self.T_summary_max:,})")

            shrink_response = self.client.responses.create(
                model=self.model,
                previous_response_id=branch_id,
                input=[{
                    "role": "user",
                    "content": f"Too long ({len(summary_text):,} chars). Compress to under {self.T_summary_max:,}. Output ONLY the shorter summary."
                }]
            )

            self._track_token_usage(shrink_response, "shrink")
            new_text = shrink_response.output_text
            if len(new_text) >= len(summary_text):
                # Hard truncate
                summary_text = summary_text[:self.T_summary_max - 50] + "\n[...truncated...]"
                break
            summary_text = new_text
            branch_id = shrink_response.id

        self.current_summary = summary_text
        self.summary_anchor_idx = anchor_idx  # Summary covers up to anchor
        summary_logger.info(f"[SUMMARY] Stored | {len(summary_text):,} chars | covers msgs 1-{anchor_idx}")

        # Dump to disk if summaries_dir is set
        if self.summaries_dir:
            self.summaries_dir.mkdir(parents=True, exist_ok=True)
            timestamp_file = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_file = self.summaries_dir / f"summary_{timestamp_file}_anchor{anchor_idx}.md"
            summary_file.write_text(summary_text)
            summary_logger.info(f"[SUMMARY] Saved to {summary_file}")

    def _calculate_drain_anchor(self) -> tuple[int, int, int]:
        """Calculate drain anchor point (ALL SIZES IN TOKENS).

        Uses T_summary_max as the expected summary size (worst-case).
        This ensures predictable, conservative calculations.

        IMPORTANT: Always keeps at least the last message, even if it's huge.
        The anchor is the index of the LAST message to DELETE.
        Messages from anchor+1 onwards are KEPT.

        Returns:
            (new_anchor_idx, overhead_tokens, accumulated_tokens)
        """
        # Estimate tokens for system prompt
        system_tokens = self._estimate_tokens(self.messages[0].content)

        # Use T_summary_max as worst-case summary size (already in tokens)
        summary_tokens = self.T_summary_max
        overhead_tokens = system_tokens + summary_tokens + 100  # 100 token buffer

        available_tokens = self.T_target - overhead_tokens
        accumulated_tokens = 0

        # Start from second-to-last message and work backwards
        # This GUARANTEES we always keep at least the last message
        last_msg_idx = len(self.messages) - 1

        # If we only have system + 1 message, can't delete anything meaningful
        if last_msg_idx <= 1:
            msg_tokens = self._estimate_tokens(self.messages[1].content) if last_msg_idx >= 1 else 0
            return 1, overhead_tokens, msg_tokens

        # Always include the last message in "kept" messages
        last_msg_tokens = self._estimate_tokens(self.messages[last_msg_idx].content)
        accumulated_tokens = last_msg_tokens

        # Default: delete everything except the last message
        # anchor = last_msg_idx - 1 means "delete 1 to last-1, keep last"
        new_anchor_idx = last_msg_idx - 1

        # Try to keep more messages if they fit
        for i in range(last_msg_idx - 1, 0, -1):
            msg_tokens = self._estimate_tokens(self.messages[i].content)
            if accumulated_tokens + msg_tokens > available_tokens:
                # Can't fit this message - anchor stays at i (delete 1 to i)
                new_anchor_idx = i
                break
            accumulated_tokens += msg_tokens
            new_anchor_idx = i - 1  # Can keep this message too

        return max(new_anchor_idx, 1), overhead_tokens, accumulated_tokens

    def get_stats(self) -> dict:
        """Get current stats."""
        effective_tokens = self._get_effective_tokens()
        return {
            # Primary metrics - NOW IN TOKENS
            "T_current": effective_tokens,  # For backwards compat, now means tokens
            "T_current_tokens": self.T_current_tokens,
            "T_current_chars": self.T_current_chars,
            "tokens_calibrated": self.tokens_calibrated,
            "T_max": self.T_max,
            "T_target": self.T_target,
            "T_summary_max": self.T_summary_max,
            # Message stats
            "message_count": len(self.messages),
            "checkpoint_count": len(self.checkpoints),
            "summary_count": 1 if self.current_summary else 0,
            "has_summary": self.current_summary is not None,
            "summary_size": len(self.current_summary) if self.current_summary else 0,
            "current_anchor_idx": self.current_anchor_idx,
            "has_response_id": self.last_response_id is not None,
            "summarization_in_progress": False,  # V3 is synchronous
            # Cumulative token usage (for billing/stats)
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cached_tokens": self.total_cached_tokens,
            "api_call_count": self.api_call_count,
        }

    # --- Agent integration methods ---
    # These allow external agents to use the context manager while handling their own LLM calls

    def add_user_message(self, content: str) -> None:
        """
        Add a user message to the context.
        Checks for drain if context exceeds T_max.
        """
        if len(content) > self.max_message_size:
            raise ValueError(f"Message too large: {len(content):,} chars")

        self.messages.append(Message(role=MessageRole.USER, content=content))
        self.T_current_chars += len(content)

        # Estimate tokens for new message
        msg_tokens = self._estimate_tokens(content)
        if not self.tokens_calibrated:
            self.T_current_tokens += msg_tokens

        # Count towards checkpoint threshold
        self.tokens_since_checkpoint += msg_tokens

        effective_tokens = self._get_effective_tokens()
        calibration_status = "actual" if self.tokens_calibrated else "est"
        summary_logger.info(
            f"[CONTEXT] +USER (~{msg_tokens:,} tokens) → "
            f"T_current={effective_tokens:,}/{self.T_max:,} tokens ({effective_tokens/self.T_max*100:.1f}%) [{calibration_status}]"
        )

        # Save checkpoint if we've accumulated enough tokens
        if self.last_response_id and self.tokens_since_checkpoint >= self.checkpoint_interval:
            self._save_checkpoint()

        # Check if we need to drain
        if effective_tokens > self.T_max:
            # CRITICAL: Save checkpoint right before drain if we have a response_id
            # This ensures we ALWAYS have a checkpoint to branch from for summary!
            if self.last_response_id and not self.checkpoints:
                summary_logger.info("[CHECKPOINT] Saving emergency checkpoint before drain")
                self._save_checkpoint()
            self._drain_context()

    def add_assistant_message(self, content: str, response_id: str | None = None) -> None:
        """
        Add an assistant message to the context.
        Optionally stores the response_id for continuation mode.
        Saves checkpoint if enough content accumulated.
        """
        self.messages.append(Message(role=MessageRole.ASSISTANT, content=content))
        self.T_current_chars += len(content)

        # Estimate tokens for new message
        msg_tokens = self._estimate_tokens(content)
        if not self.tokens_calibrated:
            self.T_current_tokens += msg_tokens

        if response_id is not None:
            self.last_response_id = response_id

        effective_tokens = self._get_effective_tokens()
        calibration_status = "actual" if self.tokens_calibrated else "est"
        summary_logger.info(
            f"[CONTEXT] +ASST (~{msg_tokens:,} tokens) → "
            f"T_current={effective_tokens:,}/{self.T_max:,} tokens ({effective_tokens/self.T_max*100:.1f}%) [{calibration_status}]"
        )

        # Maybe save checkpoint
        self._maybe_save_checkpoint(msg_tokens)

    def get_llm_input(self) -> tuple[list[dict], str | None]:
        """
        Get the input messages and previous_response_id for an LLM call.

        Returns:
            tuple of (input_messages, previous_response_id)
            - If previous_response_id is not None, input_messages contains only the last message
            - If previous_response_id is None, input_messages contains full context
        """
        llm_input = self._build_llm_input()

        if self.last_response_id is not None:
            summary_logger.debug(f"[LLM_INPUT] Continuation mode | {len(llm_input)} msg(s)")
        elif self.current_anchor_idx is not None:
            summary_logger.debug(f"[LLM_INPUT] Post-drain mode | {len(llm_input)} msg(s)")
        else:
            summary_logger.debug(f"[LLM_INPUT] Fresh context | {len(llm_input)} msg(s)")

        return llm_input, self.last_response_id

    def set_response_id(self, response_id: str) -> None:
        """Set the last response ID without adding a message."""
        self.last_response_id = response_id
