"""`loco list` — enumerate runtimes, models, configs, and benchmarks."""
from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from llm_cli.core import registry
from llm_cli.core.model_registry import RegistryEntry, load_registry
from llm_cli.core.settings import load_settings, resolve

console = Console()


def _summarize(item: Any) -> dict[str, Any]:
    if isinstance(item, registry.RuntimeRecord):
        return {
            "id": item.id,
            "kind": "runtime",
            "path": str(item.path),
            "source": item.source,
        }
    if isinstance(item, RegistryEntry):
        return {"id": item.id, "kind": "model", "format": item.format, "source": item.source.kind}
    if isinstance(item, registry.ConfigRecord):
        return {
            "id": item.id,
            "kind": "config",
            "path": str(item.path),
            "source": item.source,
            "runtime": item.data.get("runtime"),
            "model": item.data.get("model"),
        }
    if isinstance(item, registry.BenchmarkRecord):
        return {
            "id": item.id,
            "kind": "benchmark",
            "path": str(item.path),
            "source": item.source,
            "needs_server": item.bench.get("needs_server", True),
        }
    raise TypeError(item)


def _runtime_display_id(runtime_id: str) -> str:
    if registry.runtime_overrides_scaffold(runtime_id):
        return f"{runtime_id} (overrides scaffold)"
    return runtime_id


def list_entities(
    what: str | None = typer.Argument(
        None,
        help="Optional filter: runtimes | models | configs | benchmarks.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of a table."),
) -> None:
    """List runtimes, models, configs, and/or benchmarks discovered in the repo."""
    filters = {"runtimes", "models", "configs", "benchmarks"}
    if what is not None and what not in filters:
        console.print(
            f"[red]error:[/red] unknown kind {what!r} (choose from {', '.join(sorted(filters))})"
        )
        raise typer.Exit(code=1)

    runtimes = registry.discover_runtimes_merged()
    settings = resolve(load_settings())
    models = sorted(load_registry(settings.models_dir).values(), key=lambda e: e.id)
    configs = registry.discover_configs_merged()
    benches = registry.discover_benchmarks_merged()

    sections: list[tuple[str, list[Any]]] = []
    if what is None or what == "runtimes":
        sections.append(("runtimes", list(runtimes)))
    if what is None or what == "models":
        sections.append(("models", list(models)))
    if what is None or what == "configs":
        sections.append(("configs", list(configs)))
    if what is None or what == "benchmarks":
        sections.append(("benchmarks", list(benches)))

    if as_json:
        payload: list[dict[str, Any]] = []
        for _, rows in sections:
            for row in rows:
                payload.append(_summarize(row))
        typer.echo(json.dumps(payload, indent=2))
        return

    for title, rows in sections:
        table = Table(title=title.capitalize())
        if not rows:
            console.print(f"[dim]{title}: (none)[/dim]")
            continue
        if title == "runtimes":
            table.add_column("ID")
            table.add_column("Display name")
            table.add_column("Source")
            for r in rows:
                assert isinstance(r, registry.RuntimeRecord)
                dn = str(r.manifest.get("display_name", ""))
                table.add_row(_runtime_display_id(r.id), dn, r.source)
        elif title == "models":
            table.add_column("ID")
            table.add_column("Format")
            table.add_column("Source")
            table.add_column("Display name")
            for m in rows:
                assert isinstance(m, RegistryEntry)
                table.add_row(m.id, m.format, m.source.kind, m.metadata.display_name)
        elif title == "configs":
            table.add_column("ID")
            table.add_column("Runtime")
            table.add_column("Model")
            table.add_column("Source")
            for c in rows:
                assert isinstance(c, registry.ConfigRecord)
                table.add_row(
                    c.id,
                    str(c.data.get("runtime", "")),
                    str(c.data.get("model", "")),
                    c.source,
                )
        elif title == "benchmarks":
            table.add_column("ID")
            table.add_column("Needs server")
            table.add_column("Source")
            for b in rows:
                assert isinstance(b, registry.BenchmarkRecord)
                table.add_row(
                    b.id,
                    str(b.bench.get("needs_server", True)),
                    b.source,
                )
        console.print(table)
