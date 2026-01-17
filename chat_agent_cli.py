#!/usr/bin/env python3
"""
Interactive CLI for the Chat Agent.

Usage:
    python chat_agent_cli.py --cdp-captures-dir ./cdp_captures

Commands:
    /stats  - Show context stats
    /logs   - Show context manager logs
    /clear  - Clear conversation (start fresh)
    /quit   - Exit
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.markup import escape
from rich.syntax import Syntax
from rich import box

from llm_context_manager_v3 import summary_logger

# Setup log capture BEFORE importing chat_agent (which imports the context manager)
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

# Now import chat_agent
from web_hacker.routine_discovery.chat_agent import create_chat_agent, SYSTEM_PROMPT_BASE

console = Console()


def permission_callback(tool_name: str, tool_args: dict) -> bool:
    """
    Prompt user for permission before executing a tool.

    Args:
        tool_name: Name of the tool being called
        tool_args: Arguments passed to the tool

    Returns:
        True if user grants permission, False otherwise
    """
    console.print()
    console.print(Panel(
        f"[bold yellow]⚠️  Tool Execution Request[/bold yellow]",
        style="yellow"
    ))

    console.print(f"[bold]Tool:[/bold] [cyan]{tool_name}[/cyan]")

    # Show tool arguments in a pretty format
    if tool_args:
        # For routines, show a summary
        if "routine" in tool_args:
            routine = tool_args["routine"]
            console.print(f"\n[bold]Routine:[/bold]")
            console.print(f"  Name: [green]{routine.get('name', 'N/A')}[/green]")
            console.print(f"  Description: {routine.get('description', 'N/A')}")

            ops = routine.get("operations", [])
            console.print(f"  Operations: [cyan]{len(ops)}[/cyan]")
            for i, op in enumerate(ops[:5]):  # Show first 5 ops
                op_type = op.get("type", "unknown")
                console.print(f"    {i+1}. [dim]{op_type}[/dim]")
            if len(ops) > 5:
                console.print(f"    [dim]... and {len(ops) - 5} more[/dim]")

        if "parameters" in tool_args and tool_args["parameters"]:
            console.print(f"\n[bold]Parameters:[/bold]")
            params_json = json.dumps(tool_args["parameters"], indent=2)
            console.print(Syntax(params_json, "json", theme="monokai", line_numbers=False))
    else:
        console.print("[dim]No arguments[/dim]")

    console.print()

    # Prompt for permission
    try:
        response = console.input("[bold]Allow this tool to execute? [/bold][green](y)[/green]/[red](n)[/red]: ").strip().lower()
        allowed = response in ("y", "yes", "")
        if allowed:
            console.print("[green]✓ Permission granted[/green]")
        else:
            console.print("[red]✗ Permission denied[/red]")
        console.print()
        return allowed
    except (EOFError, KeyboardInterrupt):
        console.print("\n[red]✗ Permission denied (interrupted)[/red]")
        return False


def print_stats(agent) -> None:
    """Print current context manager stats."""
    stats = agent.get_stats()

    t_current = stats["T_current"]
    t_max = stats["T_max"]
    t_target = stats["T_target"]

    # determine color based on thresholds
    if t_current > t_max:
        color = "red bold"
        status = "OVER MAX - WILL DRAIN"
    elif t_current > t_max * 0.8:
        color = "yellow"
        status = "APPROACHING MAX"
    elif t_current > t_target:
        color = "cyan"
        status = "NORMAL"
    else:
        color = "green"
        status = "LOW"

    table = Table(title="Chat Agent Context Stats", box=box.ROUNDED)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_column("Status", justify="center")

    # context size row with bar
    pct_of_max = min(t_current / t_max * 100, 100)
    bar_width = 30
    filled = int(pct_of_max / 100 * bar_width)
    bar = "█" * filled + "░" * (bar_width - filled)

    table.add_row(
        "T_current",
        f"[{color}]{t_current:,}[/{color}]",
        f"[{color}]{bar} {pct_of_max:.1f}%[/{color}]"
    )
    table.add_row("T_target", f"{t_target:,}", "[dim]target after drain[/dim]")
    table.add_row("T_max", f"{t_max:,}", "[dim]drain threshold[/dim]")
    table.add_row("T_summary_max", f"{stats['T_summary_max']:,}", "[dim]max summary size[/dim]")
    table.add_row("", "", "")
    table.add_row("Messages", str(stats["message_count"]), "")
    table.add_row("Checkpoints", str(stats.get("checkpoint_count", 0)), "[dim]saved branch points[/dim]")
    table.add_row("Summary", f"{stats.get('summary_size', 0):,} chars" if stats.get("has_summary") else "None", "")
    table.add_row("Has Response ID", "✓" if stats["has_response_id"] else "✗",
                  "[green]continuation mode[/green]" if stats["has_response_id"] else "[yellow]fresh context[/yellow]")

    console.print()
    console.print(table)
    console.print(f"\n[bold]Status:[/bold] [{color}]{status}[/{color}]")
    console.print()


def print_logs() -> None:
    """Print captured context manager logs."""
    console.print()
    console.print(Panel("[bold]Context Manager Logs[/bold]", style="red"))

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


def print_help() -> None:
    """Print help."""
    console.print()
    console.print(Panel(
        """[bold]Commands:[/bold]
  [cyan]/stats[/cyan]   - Show current context stats
  [cyan]/logs[/cyan]    - Show context manager logs
  [cyan]/clear[/cyan]   - Clear conversation (start fresh)
  [cyan]/help[/cyan]    - Show this help
  [cyan]/quit[/cyan]    - Exit

[bold]Ask me anything about:[/bold]
  • Routines, operations, parameters, placeholders
  • How to build automations
  • What happened in your browser session (CDP captures)
  • Debugging routine issues

[bold]Agent Tools:[/bold]
  • [green]validate_routine[/green] - Validate a routine JSON (creates Routine instance)
  • [green]execute_routine[/green] - Execute a routine (requires Chrome on port 9222)

[dim]Tool execution requires your permission before running.[/dim]""",
        title="Chat Agent CLI",
        style="blue"
    ))
    console.print()


def main():
    parser = argparse.ArgumentParser(description="Chat Agent CLI")
    parser.add_argument(
        "--cdp-captures-dir",
        type=str,
        required=True,
        help="Path to CDP captures directory",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5.1",
        help="LLM model to use (default: gpt-5.1)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for summaries",
    )

    args = parser.parse_args()

    # Validate captures dir
    cdp_path = Path(args.cdp_captures_dir)
    if not cdp_path.exists():
        console.print(f"[red]Error: CDP captures directory not found: {cdp_path}[/red]")
        sys.exit(1)

    console.print()
    console.print("[bold blue]═══════════════════════════════════════════════════════════════[/bold blue]")
    console.print("[bold blue]              Chat Agent - Web Hacker Assistant                [/bold blue]")
    console.print("[bold blue]═══════════════════════════════════════════════════════════════[/bold blue]")
    console.print()

    console.print(f"[dim]CDP captures: {cdp_path}[/dim]")
    console.print(f"[dim]Model: {args.model}[/dim]")
    console.print()

    console.print("[yellow]⏳ Initializing (loading docs + captures into vectorstore)...[/yellow]")

    try:
        agent = create_chat_agent(
            cdp_captures_dir=str(cdp_path),
            llm_model=args.model,
            output_dir=args.output_dir,
        )
        # Set permission callback for tool execution
        agent.permission_callback = permission_callback
        agent.initialize()
    except Exception as e:
        console.print(f"[red]Error initializing agent: {e}[/red]")
        sys.exit(1)

    console.print("[green]✓ Chat Agent ready![/green]")
    console.print()
    print_help()

    try:
        while True:
            # Show mini status in prompt
            stats = agent.get_stats()
            t_pct = stats["T_current"] / stats["T_max"] * 100

            if t_pct > 100:
                status_color = "red"
            elif t_pct > 80:
                status_color = "yellow"
            else:
                status_color = "green"

            console.print(f"[dim][{status_color}]{stats['T_current']:,}/{stats['T_max']:,} ({t_pct:.0f}%)[/{status_color}][/dim]", end=" ")

            try:
                user_input = console.input("[bold green]You>[/bold green] ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            # Handle commands
            if user_input.startswith("/"):
                cmd = user_input.lower()

                if cmd in ("/quit", "/exit", "/q"):
                    break
                elif cmd == "/stats":
                    print_stats(agent)
                    continue
                elif cmd == "/logs":
                    print_logs()
                    continue
                elif cmd == "/clear":
                    # Rebuild system prompt with docs index
                    from web_hacker.routine_discovery.chat_agent import DOCS_INDEX_HEADER
                    system_prompt = SYSTEM_PROMPT_BASE
                    if agent.context_manager.docs_index:
                        system_prompt += DOCS_INDEX_HEADER + agent.context_manager.docs_index
                    agent.llm_context.start_session(system_prompt)
                    log_capture.clear()
                    console.print("[yellow]✓ Conversation cleared.[/yellow]")
                    continue
                elif cmd == "/help":
                    print_help()
                    continue
                else:
                    console.print(f"[red]Unknown command: {cmd}[/red]")
                    console.print("[dim]Type /help for available commands[/dim]")
                    continue

            # Regular message - send to LLM
            console.print()
            console.print("[dim]Sending to LLM...[/dim]")

            # Capture pre-call stats
            pre_stats = agent.get_stats()

            try:
                response = agent.chat(user_input)

                # Show response with Markdown rendering
                console.print()
                console.print("[bold cyan]Assistant>[/bold cyan]")
                console.print(Markdown(response))
                console.print()

                # Show post-call stats delta (like llm_context_manager_cli.py)
                post_stats = agent.get_stats()
                delta = post_stats["T_current"] - pre_stats["T_current"]

                console.print(f"[dim]─────────────────────────────────────────────────────[/dim]")
                console.print(f"[dim]Context: {pre_stats['T_current']:,} → {post_stats['T_current']:,} (+{delta:,} chars)[/dim]")

                if post_stats.get("summarization_in_progress"):
                    console.print("[yellow]⏳ Async summarization in progress...[/yellow]")

                if pre_stats["has_response_id"] != post_stats["has_response_id"]:
                    if post_stats["has_response_id"]:
                        console.print("[green]🔗 Now in continuation mode[/green]")
                    else:
                        console.print("[yellow]⚠️ Context was drained - fresh start[/yellow]")

                if pre_stats.get("current_anchor_idx") != post_stats.get("current_anchor_idx"):
                    console.print(f"[yellow]📍 Anchor moved: {pre_stats.get('current_anchor_idx')} → {post_stats.get('current_anchor_idx')}[/yellow]")

                if pre_stats.get("has_summary") != post_stats.get("has_summary") and post_stats.get("has_summary"):
                    console.print(f"[green]📝 New summary generated![/green]")

                console.print()

            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

    except KeyboardInterrupt:
        console.print("\n")

    # Cleanup
    console.print("[dim]Cleaning up...[/dim]")
    agent.cleanup()
    console.print("[yellow]Goodbye![/yellow]")


if __name__ == "__main__":
    main()
