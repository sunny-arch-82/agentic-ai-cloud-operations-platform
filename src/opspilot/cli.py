"""Small complete developer commands; run from the extracted repository root."""

import argparse
import asyncio
import json
from pathlib import Path

from alembic import command
from alembic.config import Config

from opspilot.core.config import Settings
from opspilot.core.logging import configure
from opspilot.evaluation import (
    evaluate_answers,
    evaluate_investigations,
    evaluate_retrieval,
    scenario_request,
)
from opspilot.mcp.client import connect_tools
from opspilot.rag.ingestion import ingest
from opspilot.services.investigations import investigate
from opspilot.storage.db import Database
from opspilot.storage.fixtures import seed_operational


async def dispatch(args, settings, db):
    if args.command in {"bootstrap", "ingest"}:
        if settings.mode == "openai" and not args.allow_paid:
            raise ValueError("Use --allow-paid to authorize embedding API calls")
        if args.command == "bootstrap":
            command.upgrade(Config("alembic.ini"), "head")
            fixtures = await asyncio.to_thread(seed_operational, db, settings.data_dir)
        else:
            fixtures = None
        return {"fixtures": fixtures, "ingestion": await ingest(db, settings)}
    if args.command == "demo":
        if settings.mode == "openai" and not args.allow_paid:
            raise ValueError("Use --allow-paid to authorize model/embedding API calls")
        return (await investigate(db, settings, scenario_request(args.scenario))).model_dump(
            mode="json"
        )
    if args.command == "mcp-check":
        async with asyncio.timeout(30):
            async with connect_tools(settings) as tools:
                available = await tools.list_tools()
                request = scenario_request()
                result = await tools.call(
                    "fetch_service_metrics",
                    {
                        "dataset_id": request.dataset_id,
                        "service": request.service,
                        "start": request.time_window.start.isoformat(),
                        "end": request.time_window.end.isoformat(),
                        "reference_time": request.reference_time.isoformat(),
                    },
                )
                return {
                    "transport": "MCP stdio",
                    "tools": [
                        {
                            "name": t.name,
                            "input_schema": t.inputSchema,
                            "output_schema": t.outputSchema,
                        }
                        for t in available
                    ],
                    "evidence_count": len(result.evidence),
                    "sample_count": result.evidence[0].data["sample_count"],
                }
    if args.command == "eval":
        if settings.mode == "openai" and not args.allow_paid:
            raise ValueError("Use --allow-paid to authorize evaluation API calls")
        if args.kind == "investigations":
            return await evaluate_investigations(db, settings)
        function = evaluate_retrieval if args.kind == "retrieval" else evaluate_answers
        return await function(db, settings, args.split)
    raise ValueError("Unknown command")


def main():
    parser = argparse.ArgumentParser(description="OpsPilot developer CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["bootstrap", "ingest", "demo", "mcp-check", "eval"]:
        item = sub.add_parser(name)
        item.add_argument("--output", type=Path)
        item.add_argument("--allow-paid", action="store_true")
        if name == "demo":
            item.add_argument("--scenario", choices=[f"s0{i}" for i in range(1, 7)], default="s01")
        if name == "eval":
            item.add_argument(
                "--kind", choices=["retrieval", "answers", "investigations"], default="retrieval"
            )
            item.add_argument("--split", choices=["all", "dev", "test"], default="all")
    args = parser.parse_args()
    settings = Settings()
    configure(settings.log_level)
    db = Database(settings)
    try:
        result = asyncio.run(dispatch(args, settings, db))
        output = json.dumps(result, indent=2, default=str) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output)
            print(json.dumps({"saved": str(args.output)}))
        else:
            print(output)
    except Exception as exc:
        parser.exit(
            1,
            f"OpsPilot command failed ({type(exc).__name__}). Check configuration, migrations, provider access, and logs.\n",
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
