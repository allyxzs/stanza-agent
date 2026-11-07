import asyncio
import json
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from stanza.core.orchestrator import StanzaAutonomousAgent
from stanza.config.settings import settings

app = typer.Typer(
    name="stanza",
    help="Stanza Agent v3.0 CLI - Autonomous Linguistic, Structural & Semantic Reasoning Engine",
    add_completion=False,
)
console = Console()


@app.command()
def info():
    """Display Stanza Agent v3.0 architecture telemetry and subsystem status."""
    agent = StanzaAutonomousAgent(db_path=settings.db_path, ledger_path=settings.ledger_path)
    integrity = agent.ledger.verify_integrity()

    table = Table(title="Stanza Agent v3.0 Subsystem Matrix", show_header=True, header_style="bold cyan")
    table.add_column("Subsystem", style="bold white")
    table.add_column("Architecture", style="green")
    table.add_column("Status", style="bold yellow")

    table.add_row("Zero-Trust Shield", "Regex Heuristics + Shannon Entropy Inspector", "ACTIVE")
    table.add_row("Linguistic Engine", "Neuro-Symbolic Stanza Segmenter + Python AST Inspector", "ACTIVE")
    table.add_row("Cognitive Memory", "SQLite 3-Tier (BM25 + Cosine Vector + Temporal Decay)", "ACTIVE")
    table.add_row("DAG Orchestrator", "Async Topological Sort + Self-Healing Daemon", "ACTIVE")
    table.add_row(
        "Cryptographic Ledger",
        f"HMAC-SHA256 + Merkle Root ({integrity['total_blocks']} blocks)",
        "VERIFIED" if integrity["valid"] else "CORRUPTED",
    )

    console.print(Panel.fit("[bold magenta]STANZA AGENT v3.0 — SOVEREIGN EDITION[/bold magenta]", border_style="cyan"))
    console.print(table)


@app.command()
def run(
    prompt: str = typer.Argument(..., help="Mission prompt or text to process"),
    code: str = typer.Option("", "--code", "-c", help="Optional Python snippet for AST analysis"),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON telemetry"),
):
    """Execute an autonomous multi-stage DAG mission through Stanza Agent v3.0."""
    agent = StanzaAutonomousAgent(db_path=settings.db_path, ledger_path=settings.ledger_path)
    result = asyncio.run(agent.process_mission(prompt=prompt, code_snippet=code if code else None))

    if json_out:
        console.print_json(data=result)
        return

    console.print(Panel(f"[bold cyan]Status:[/bold cyan] {result['status']}", title="Stanza Mission Verdict"))
    if result["status"] == "SUCCESS":
        console.print(f"[bold green]Primary Intent:[/bold green] {result['synthesis']['primary_intent']}")
        console.print(f"[bold green]Summary:[/bold green] {result['synthesis']['summary']}")
        console.print(f"[bold yellow]Merkle Root:[/bold yellow] {result['cryptographic_proof']['merkle_root']}")
        console.print(f"[bold yellow]Block Hash:[/bold yellow] {result['cryptographic_proof']['block_hash']}")
    else:
        console.print(f"[bold red]Blocked Threat Vectors:[/bold red] {result['security_verdict']['detected_vectors']}")


@app.command()
def audit():
    """Verify the cryptographic integrity of the local HMAC-SHA256 & Merkle Audit Ledger."""
    agent = StanzaAutonomousAgent(db_path=settings.db_path, ledger_path=settings.ledger_path)
    report = agent.ledger.verify_integrity()
    console.print_json(data=report)


if __name__ == "__main__":
    app()
