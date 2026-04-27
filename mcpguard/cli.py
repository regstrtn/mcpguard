"""mcpguard.cli — Command-line interface.

Commands:
  mcpguard run --config mcpguard.yaml -- <upstream_command>
  mcpguard run --shadow -- <upstream_command>   (log only, never block)
  mcpguard validate --config mcpguard.yaml
  mcpguard stats --log mcpguard_audit.jsonl
  mcpguard init
  mcpguard test --config mcpguard.yaml --tool <name> --args '{"key": "val"}'
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from mcpguard.audit import AuditLogger
from mcpguard.exceptions import McpGuardError
from mcpguard.policy import Action, PolicyEngine

console = Console(stderr=True)


@click.group()
@click.version_option(package_name="mcpguard")
def main() -> None:
    """mcpguard — A firewall for MCP-based AI agents."""


@main.command()
@click.option("--config", "-c", default="mcpguard.yaml", help="Policy file path")
def validate(config: str) -> None:
    """Validate a policy file for correctness."""
    try:
        engine = PolicyEngine.from_yaml(config)
    except McpGuardError as e:
        console.print(f"[red]❌ Error:[/red] {e}")
        sys.exit(1)

    warnings = engine.validate()
    if warnings:
        for w in warnings:
            console.print(f"[yellow]⚠️  {w}[/yellow]")
        sys.exit(1)

    n = len(engine.policies)
    console.print(f"[green]✅ Valid![/green] {n} policies loaded from {config}")
    console.print(f"   Default action: {engine.default_action.value}")
    for p in engine.policies:
        status = "✓" if p.enabled else "✗"
        console.print(
            f"   [{status}] {p.name} (priority={p.priority}, action={p.action.value}, "
            f"tools={p.tools})"
        )


@main.command()
@click.option("--config", "-c", default="mcpguard.yaml", help="Policy file path")
@click.option("--tool", "-t", required=True, help="Tool name to test")
@click.option("--args", "-a", default="{}", help="JSON arguments string")
def test(config: str, tool: str, args: str) -> None:
    """Test a single tool call against policies (offline, no server)."""
    try:
        engine = PolicyEngine.from_yaml(config)
    except McpGuardError as e:
        console.print(f"[red]❌ Error:[/red] {e}")
        sys.exit(1)

    try:
        arguments = json.loads(args)
    except json.JSONDecodeError as e:
        console.print(f"[red]❌ Invalid JSON args:[/red] {e}")
        sys.exit(1)

    result = engine.evaluate(tool, arguments)

    color = {
        Action.ALLOW: "green",
        Action.DENY: "red",
        Action.APPROVE: "cyan",
        Action.LOG: "blue",
    }.get(result.action, "white")

    console.print(f"\n[{color}]{result.action.value}[/{color}]", highlight=False)
    if result.matched_policy:
        console.print(f"  Policy: {result.matched_policy}")
    if result.reason:
        console.print(f"  Reason: {result.reason}")
    console.print(f"  Tool:   {tool}")
    console.print(f"  Args:   {json.dumps(arguments, indent=2)}")


@main.command()
@click.option("--log", "-l", default="mcpguard_audit.jsonl", help="Audit log path")
@click.option("--html", "-h", default=None, help="Save to HTML dashboard")
def stats(log: str, html: str | None) -> None:
    """Show summary statistics from the audit log."""
    logger = AuditLogger(path=log, also_stderr=False)
    data = logger.get_stats()

    if data["total"] == 0:
        console.print("[yellow]No audit events found.[/yellow]")
        return

    console.print(f"\n[bold]mcpguard Audit Summary[/bold] ({data['total']} events)\n")

    # By action
    table = Table(title="By Action")
    table.add_column("Action", style="bold")
    table.add_column("Count", justify="right")
    for action, count in sorted(data["by_action"].items()):
        color = {"ALLOW": "green", "DENY": "red", "LOG": "blue"}.get(
            action, "white"
        )
        table.add_row(f"[{color}]{action}[/{color}]", str(count))
    console.print(table)

    # By tool
    table = Table(title="By Tool")
    table.add_column("Tool", style="bold")
    table.add_column("Count", justify="right")
    for tool, count in sorted(data["by_tool"].items(), key=lambda x: -x[1]):
        table.add_row(tool, str(count))
    console.print(table)

    # By policy
    table = Table(title="By Policy")
    table.add_column("Policy", style="bold")
    table.add_column("Count", justify="right")
    for policy, count in sorted(data["by_policy"].items(), key=lambda x: -x[1]):
        table.add_row(policy, str(count))
    console.print(table)

    # Chain verification
    is_valid, n_checked = logger.verify_chain()
    if is_valid:
        console.print(f"\n[green]🔗 Hash chain verified ({n_checked} entries)[/green]")
    else:
        console.print(
            f"\n[red]⚠️  Hash chain broken at entry {n_checked}! Log may be tampered.[/red]"
        )

    if html:
        from mcpguard.dashboard import generate_html_dashboard
        generate_html_dashboard(data, html)
        console.print(f"\n[green]📊 Dashboard saved to {html}[/green]")


@main.command()
@click.option("--output", "-o", default="mcpguard.yaml", help="Output file path")
def init(output: str) -> None:
    """Generate a starter policy file."""
    source = Path(__file__).parent.parent / "mcpguard.yaml"

    if not source.exists():
        console.print(f"[red]❌ Bundled mcpguard.yaml not found[/red]")
        sys.exit(1)

    dest = Path(output)
    if dest.exists():
        if not click.confirm(f"{dest} already exists. Overwrite?"):
            return

    dest.write_text(source.read_text())
    console.print(f"[green]✅ Created {dest}[/green]")
    console.print(f"   Edit the file, then run: mcpguard validate --config {dest}")


@main.command()
@click.option("--config", "-c", default="mcpguard.yaml", help="Policy file path")
@click.option("--log", "-l", default="mcpguard_audit.jsonl", help="Audit log path")
@click.option("--shadow", is_flag=True, default=False, help="Shadow mode: log everything, block nothing")
@click.argument("upstream_command", nargs=-1, required=True)
def run(config: str, log: str, shadow: bool, upstream_command: tuple[str, ...]) -> None:
    """Start the mcpguard proxy in front of an MCP server.

    Usage: mcpguard run --config mcpguard.yaml -- npx @anthropic/mcp-filesystem /tmp
    Shadow: mcpguard run --shadow -- npx @anthropic/mcp-filesystem /tmp
    """
    # Import here to avoid circular / heavy imports at CLI load time
    import asyncio

    from mcpguard.proxy import McpProxy

    try:
        engine = PolicyEngine.from_yaml(config)
    except McpGuardError as e:
        console.print(f"[red]❌ Error:[/red] {e}")
        sys.exit(1)

    audit_logger = AuditLogger(path=log)
    proxy = McpProxy(
        upstream_command=list(upstream_command),
        policy_engine=engine,
        audit_logger=audit_logger,
        shadow_mode=shadow,
    )

    mode_label = "[yellow]SHADOW[/yellow]" if shadow else "[green]ENFORCE[/green]"
    console.print(f"[bold]mcpguard[/bold] starting proxy ({mode_label})")
    if shadow:
        console.print(f"  ⚡ Shadow mode: all calls logged, nothing blocked")
    console.print(f"  Config:   {config}")
    console.print(f"  Upstream: {' '.join(upstream_command)}")
    console.print(f"  Policies: {len(engine.policies)} loaded")
    console.print(f"  Default:  {engine.default_action.value}")
    console.print(f"  Log:      {log}")
    console.print()

    try:
        asyncio.run(proxy.start())
    except KeyboardInterrupt:
        console.print("\n[yellow]mcpguard stopped[/yellow]")
