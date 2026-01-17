#!/usr/bin/env python3
"""
Interactive CLI for testing LLMContextManager.

Commands:
  /stats     - Show current context stats (T_current, T_drain, T_max, etc.)
  /tokens    - Show token usage summary (input/output/cached tokens)
  /messages  - Show all messages in context
  /active    - Show what would be sent to LLM right now
  /summary   - Show the last summary if present
  /summaries - Show all summaries
  /logs      - Show summary logs
  /drain     - Force context drain (summarize and truncate)
  /paste     - Send clipboard contents as message
  /clear     - Clear screen
  /help      - Show this help
  /quit      - Exit

Otherwise, type your message to chat with the LLM.
"""

import logging
import os
import subprocess
import sys
from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich.logging import RichHandler
from rich import box

from llm_context_manager_v3 import LLMContextManagerV3, MessageRole
from llm_context_manager_v3 import summary_logger

# setup summary logger with in-memory handler to capture logs
class LogCapture(logging.Handler):
    """Handler that captures log records in memory."""
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def clear(self) -> None:
        self.records.clear()

log_capture = LogCapture()
log_capture.setLevel(logging.DEBUG)
log_capture.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
summary_logger.addHandler(log_capture)

console = Console()


def print_stats(manager: LLMContextManagerV3) -> None:
    """Print current context manager stats."""
    stats = manager.get_stats()

    # Context tracking (now in TOKENS!)
    t_current = stats["T_current"]  # This is now tokens
    t_max = stats["T_max"]
    t_target = stats["T_target"]
    t_chars = stats.get("T_current_chars", 0)
    calibrated = stats.get("tokens_calibrated", False)

    # determine color based on thresholds
    if t_current > t_max:
        color = "red bold"
        status = "OVER MAX - WILL DRAIN"
    elif t_current > t_max * 0.8:  # 80% of max
        color = "yellow"
        status = "APPROACHING MAX"
    elif t_current > t_target:
        color = "cyan"
        status = "NORMAL"
    else:
        color = "green"
        status = "LOW"

    table = Table(title="Context Manager Stats (V3 - Token-Based)", box=box.ROUNDED)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_column("Status", justify="center")

    # context size row with bar
    pct_of_max = min(t_current / t_max * 100, 100) if t_max > 0 else 0
    bar_width = 30
    filled = int(pct_of_max / 100 * bar_width)
    bar = "█" * filled + "░" * (bar_width - filled)

    # Show calibration status
    cal_status = "[green]actual[/green]" if calibrated else "[yellow]estimated[/yellow]"

    table.add_row(
        "T_current",
        f"[{color}]{t_current:,} tokens[/{color}]",
        f"[{color}]{bar} {pct_of_max:.1f}%[/{color}]"
    )
    table.add_row("", f"[dim]({t_chars:,} chars)[/dim]", cal_status)
    table.add_row("T_target", f"{t_target:,} tokens", "[dim]target after drain[/dim]")
    table.add_row("T_max", f"{t_max:,} tokens", "[dim]drain threshold[/dim]")
    table.add_row("T_summary_max", f"{stats['T_summary_max']:,} tokens", "[dim]max summary size[/dim]")
    table.add_row("", "", "")
    table.add_row("Messages", str(stats["message_count"]), "")
    table.add_row("Checkpoints", str(stats.get("checkpoint_count", 0)), "[dim]saved branch points[/dim]")
    table.add_row("Summary", f"{stats.get('summary_size', 0):,} chars" if stats.get("has_summary") else "None", "")
    table.add_row("Anchor Index", str(stats["current_anchor_idx"] or "None"), "")
    table.add_row("Has Response ID", "✓" if stats["has_response_id"] else "✗",
                  "[green]continuation mode[/green]" if stats["has_response_id"] else "[yellow]fresh context[/yellow]")

    # Cumulative token usage section
    table.add_row("", "", "")
    table.add_row("[bold]Cumulative Usage[/bold]", "", "")
    total_input = stats.get("total_input_tokens", 0)
    total_output = stats.get("total_output_tokens", 0)
    api_calls = stats.get("api_call_count", 0)
    avg_input = total_input // api_calls if api_calls > 0 else 0

    table.add_row("Input Tokens", f"{total_input:,}", f"[dim]~{avg_input:,}/call avg[/dim]")
    table.add_row("Output Tokens", f"{total_output:,}", "")
    table.add_row("Total Billed", f"{total_input + total_output:,}", f"[dim]{api_calls} API calls[/dim]")

    console.print()
    console.print(table)
    console.print(f"\n[bold]Status:[/bold] [{color}]{status}[/{color}]")
    console.print()


def print_messages(manager: LLMContextManagerV3) -> None:
    """Print all messages in the conversation."""
    console.print()
    console.print(Panel("[bold]All Messages in History[/bold]", style="blue"))

    if not manager.messages:
        console.print("[dim]No messages yet[/dim]")
        return

    for i, msg in enumerate(manager.messages):
        # highlight anchor
        anchor_marker = ""
        if manager.current_anchor_idx is not None and i == manager.current_anchor_idx:
            anchor_marker = " [red bold]◀ ANCHOR[/red bold]"

        role_colors = {
            MessageRole.SYSTEM: "magenta",
            MessageRole.USER: "green",
            MessageRole.ASSISTANT: "cyan"
        }
        color = role_colors.get(msg.role, "white")

        # truncate long messages for display
        content = msg.content
        if len(content) > 200:
            content = content[:200] + "..."

        console.print(f"[dim][{i}][/dim] [{color} bold]{msg.role.value.upper()}[/{color} bold]{anchor_marker}")
        console.print(f"    [dim]({len(msg.content):,} chars)[/dim] {content}")
        console.print()


def print_active_context(manager: LLMContextManagerV3) -> None:
    """Print what would be sent to the LLM right now."""
    console.print()
    console.print(Panel("[bold]Active Context (what would be sent to LLM)[/bold]", style="yellow"))

    # simulate building input
    llm_input = manager._build_llm_input()

    total_chars = 0
    for i, msg in enumerate(llm_input):
        role = msg["role"]
        content = msg["content"]
        total_chars += len(content)

        role_colors = {
            "system": "magenta",
            "user": "green",
            "assistant": "cyan"
        }
        color = role_colors.get(role, "white")

        # truncate for display
        display_content = content if len(content) <= 300 else content[:300] + "..."

        console.print(f"[dim][{i}][/dim] [{color} bold]{role.upper()}[/{color} bold]")
        console.print(f"    [dim]({len(content):,} chars)[/dim]")

        # check if this is a summary injection
        if "<conversation_summary>" in content:
            console.print("    [yellow]📝 SUMMARY CONTEXT INJECTED[/yellow]")
        else:
            console.print(f"    {display_content}")
        console.print()

    console.print(f"[bold]Total active context: {total_chars:,} chars[/bold]")
    console.print()


def print_summary(manager: LLMContextManagerV3) -> None:
    """Print the current summary."""
    console.print()

    if not manager.current_summary:
        console.print(Panel("[dim]No summary yet[/dim]", title="Current Summary", style="yellow"))
        return

    escaped_summary = escape(manager.current_summary)
    console.print(Panel(
        f"[bold]Anchor Index:[/bold] {manager.summary_anchor_idx}\n\n{escaped_summary}",
        title="Current Summary",
        style="yellow"
    ))
    console.print()


def print_all_summaries(manager: LLMContextManagerV3) -> None:
    """Print summary (V3 only has one summary at a time)."""
    console.print()
    console.print(Panel("[bold]Summary (V3 uses single summary)[/bold]", style="yellow"))

    if not manager.current_summary:
        console.print("[dim]No summary yet[/dim]")
        return

    console.print(f"[bold]Summary[/bold] (covers msgs 1-{manager.summary_anchor_idx})")
    truncated = manager.current_summary[:500] + ('...' if len(manager.current_summary) > 500 else '')
    console.print(f"[dim]{escape(truncated)}[/dim]")
    console.print()


def print_logs() -> None:
    """Print captured summary logs."""
    console.print()
    console.print(Panel("[bold]Summary Logs[/bold]", style="red"))

    if not log_capture.records:
        console.print("[dim]No logs yet[/dim]")
        return

    for record in log_capture.records:
        level_colors = {
            "DEBUG": "dim",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red bold",
        }
        color = level_colors.get(record.levelname, "white")
        timestamp = log_capture.formatter.formatTime(record, datefmt="%H:%M:%S")
        console.print(f"[dim]{timestamp}[/dim] [{color}][{record.levelname}][/{color}] {record.getMessage()}")

    console.print()


def get_clipboard() -> str | None:
    """Get clipboard contents. Works on macOS."""
    try:
        result = subprocess.run(["pbpaste"], capture_output=True, text=True, check=True)
        return result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def print_tokens(manager: LLMContextManagerV3) -> None:
    """Print token usage summary."""
    stats = manager.get_stats()
    console.print()

    # Cumulative billing tokens
    total_input = stats.get("total_input_tokens", 0)
    total_output = stats.get("total_output_tokens", 0)
    api_calls = stats.get("api_call_count", 0)
    avg_input = total_input // api_calls if api_calls > 0 else 0
    avg_output = total_output // api_calls if api_calls > 0 else 0

    # Context size
    t_current = stats.get("T_current", 0)
    t_chars = stats.get("T_current_chars", 0)
    t_max = stats.get("T_max", 0)
    calibrated = stats.get("tokens_calibrated", False)

    table = Table(title="Token Usage Summary", box=box.ROUNDED)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_column("Details", justify="left")

    # Context section
    cal_status = "[green]actual[/green]" if calibrated else "[yellow]estimated[/yellow]"
    pct = (t_current / t_max * 100) if t_max > 0 else 0
    table.add_row("[bold]Context Window[/bold]", "", "")
    table.add_row("  Current", f"{t_current:,} tokens", f"{pct:.1f}% of max | {cal_status}")
    table.add_row("  Chars", f"{t_chars:,}", "[dim]for reference[/dim]")
    table.add_row("", "", "")

    # Billing section
    table.add_row("[bold]Cumulative Billing[/bold]", "", "")
    table.add_row("  Input Tokens", f"{total_input:,}", f"[dim]~{avg_input:,} avg/call[/dim]")
    table.add_row("  Output Tokens", f"{total_output:,}", f"[dim]~{avg_output:,} avg/call[/dim]")
    table.add_row("  Total Billed", f"[bold]{total_input + total_output:,}[/bold]", f"[dim]{api_calls} API calls[/dim]")
    table.add_row("", "", "")

    # Mode
    mode = "[green]continuation[/green]" if stats.get("has_response_id") else "[yellow]fresh[/yellow]"
    table.add_row("Mode", mode, "[dim]KV cache reuse[/dim]" if stats.get("has_response_id") else "")

    console.print(table)
    console.print()


def print_help() -> None:
    """Print help."""
    console.print()
    console.print(Panel(
        """[bold]Commands:[/bold]
  [cyan]/stats[/cyan]     - Show current context stats (T_current, T_drain, T_max, etc.)
  [cyan]/tokens[/cyan]    - Show token usage summary
  [cyan]/messages[/cyan]  - Show all messages in context
  [cyan]/active[/cyan]    - Show what would be sent to LLM right now
  [cyan]/summary[/cyan]   - Show the last summary if present
  [cyan]/summaries[/cyan] - Show all summaries
  [cyan]/logs[/cyan]      - Show summary logs (debug info)
  [cyan]/drain[/cyan]     - Force context drain (summarize and truncate)
  [cyan]/paste[/cyan]     - Send clipboard contents as message
  [cyan]/clear[/cyan]     - Clear screen
  [cyan]/help[/cyan]      - Show this help
  [cyan]/quit[/cyan]      - Exit

[bold]Just type to chat![/bold] The context manager handles everything automatically.""",
        title="LLM Context Manager CLI",
        style="blue"
    ))
    console.print()


def main():
    console.print()
    console.print("[bold blue]═══════════════════════════════════════════════════════════════[/bold blue]")
    console.print("[bold blue]          LLM Context Manager - Interactive CLI                [/bold blue]")
    console.print("[bold blue]═══════════════════════════════════════════════════════════════[/bold blue]")
    console.print()

    # create manager with token-based thresholds for easier testing
    # V3 uses lazy summarization via checkpoint branching
    # All thresholds are now in TOKENS (not characters)
    manager = LLMContextManagerV3(
        T_max=5_000,               # 5k tokens max (triggers drain)
        T_target=2_000,            # 2k tokens target after drain
        T_summary_max=1_000,       # 1k tokens max summary size
        checkpoint_interval=1_000  # save checkpoint every 1k tokens
    )

    # start session
    system_prompt = """You are a web automation assistant. Your PRIMARY GOAL is to help users create routines that WORK and return nice, clean, structured data.

Key priorities:
1. Build reliable routines - they must execute successfully and handle edge cases
2. Extract clean data - return well-structured JSON with consistent field names
3. Be precise with selectors, URLs, and data extraction logic
4. Test and validate routines before considering them complete

CRITICAL: You MUST heavily rely on the documentation provided to you! The docs contain essential information about:
- Routine structure and format
- Available operations and their parameters
- Placeholder syntax and usage
- Best practices and common patterns
Always consult the docs before making decisions about routine structure or operations.

IMPORTANT: After EVERY routine execution, you MUST carefully review the contents and results of the routine. If something is not correct or the data is incomplete/malformed, you MUST:
- Identify what went wrong
- Correct the routine
- Validate the fix
- Re-run to confirm it works properly

Never consider a routine complete until you have verified it produces correct, clean output.

When creating routines, focus on robustness and data quality above all else."""

    manager.start_session(system_prompt)

    console.print("[green]✓ Session started![/green]")
    console.print(f"[dim]System prompt: {len(system_prompt)} chars (~{len(system_prompt)//4} tokens est)[/dim]")
    console.print()
    print_stats(manager)
    print_help()

    while True:
        try:
            # show mini status in prompt (now in tokens!)
            stats = manager.get_stats()
            t_pct = stats["T_current"] / stats["T_max"] * 100 if stats["T_max"] > 0 else 0
            cal_marker = "" if stats.get("tokens_calibrated", False) else "~"  # ~ means estimated

            if t_pct > 100:
                status_color = "red"
            elif t_pct > 80:  # approaching max
                status_color = "yellow"
            else:
                status_color = "green"

            console.print(f"[dim][{status_color}]{cal_marker}{stats['T_current']:,}/{stats['T_max']:,} tokens ({t_pct:.0f}%)[/{status_color}][/dim]", end=" ")
            user_input = console.input("[bold green]You>[/bold green] ").strip()

            if not user_input:
                continue

            # handle commands
            if user_input.startswith("/"):
                cmd = user_input.lower()

                if cmd == "/quit" or cmd == "/exit" or cmd == "/q":
                    console.print("[yellow]Goodbye![/yellow]")
                    break
                elif cmd == "/stats":
                    print_stats(manager)
                elif cmd == "/tokens":
                    print_tokens(manager)
                elif cmd == "/messages":
                    print_messages(manager)
                elif cmd == "/active":
                    print_active_context(manager)
                elif cmd == "/summary":
                    print_summary(manager)
                elif cmd == "/summaries":
                    print_all_summaries(manager)
                elif cmd == "/logs":
                    print_logs()
                elif cmd == "/drain":
                    console.print("[yellow]⏳ Forcing context drain...[/yellow]")
                    pre_stats = manager.get_stats()
                    manager.force_drain()
                    post_stats = manager.get_stats()
                    console.print(f"[green]✓ Context drained: {pre_stats['T_current']:,} → {post_stats['T_current']:,} tokens[/green]")
                    console.print(f"[dim]Anchor moved to message {post_stats['current_anchor_idx']}[/dim]")
                    print_stats(manager)
                elif cmd == "/paste":
                    clipboard_content = get_clipboard()
                    if not clipboard_content:
                        console.print("[red]Failed to read clipboard (is it empty?)[/red]")
                        continue
                    console.print(f"[dim]📋 Clipboard: {len(clipboard_content):,} chars[/dim]")
                    # preview first 200 chars
                    preview = clipboard_content[:200] + "..." if len(clipboard_content) > 200 else clipboard_content
                    console.print(f"[dim]{preview}[/dim]")
                    user_input = clipboard_content  # fall through to send as message
                elif cmd == "/clear":
                    console.clear()
                elif cmd == "/help":
                    print_help()
                else:
                    console.print(f"[red]Unknown command: {cmd}[/red]")
                    console.print("[dim]Type /help for available commands[/dim]")
                    continue

                # commands that don't set user_input should continue
                if cmd != "/paste":
                    continue

            # regular message - send to LLM
            console.print()
            console.print("[dim]Sending to LLM...[/dim]")

            # show pre-call stats
            pre_stats = manager.get_stats()

            try:
                response = manager.get_response(user_input)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                continue

            # show response
            console.print()
            console.print("[bold cyan]Assistant>[/bold cyan]")
            console.print(Markdown(response))
            console.print()

            # show post-call stats delta
            post_stats = manager.get_stats()
            delta = post_stats["T_current"] - pre_stats["T_current"]
            calibrated = post_stats.get("tokens_calibrated", False)
            cal_status = "actual" if calibrated else "est"

            # token delta (billed tokens for this call)
            input_delta = post_stats["total_input_tokens"] - pre_stats.get("total_input_tokens", 0)
            output_delta = post_stats["total_output_tokens"] - pre_stats.get("total_output_tokens", 0)

            console.print(f"[dim]─────────────────────────────────────────────────────[/dim]")
            console.print(f"[dim]Context: {pre_stats['T_current']:,} → {post_stats['T_current']:,} tokens (+{delta:,}) [{cal_status}][/dim]")
            console.print(f"[dim]This call: in={input_delta:,} out={output_delta:,}[/dim]")

            if post_stats["summarization_in_progress"]:
                console.print("[yellow]⏳ Async summarization in progress...[/yellow]")

            if pre_stats["has_response_id"] != post_stats["has_response_id"]:
                if post_stats["has_response_id"]:
                    console.print("[green]🔗 Now in continuation mode[/green]")
                else:
                    console.print("[yellow]⚠️ Context was drained - fresh start[/yellow]")

            if pre_stats["current_anchor_idx"] != post_stats["current_anchor_idx"]:
                console.print(f"[yellow]📍 Anchor moved: {pre_stats['current_anchor_idx']} → {post_stats['current_anchor_idx']}[/yellow]")

            if pre_stats["summary_count"] != post_stats["summary_count"]:
                console.print(f"[green]📝 New summary generated! (total: {post_stats['summary_count']})[/green]")

            console.print()

        except KeyboardInterrupt:
            console.print("\n[yellow]Use /quit to exit[/yellow]")
        except EOFError:
            break


if __name__ == "__main__":
    main()
