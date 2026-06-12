from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from api.services.semantic_graph import (
    SemanticGraphUnavailable,
    build_semantic_graph,
    serialize_semantic_graph,
)


class Command(BaseCommand):
    """Export the development semantic graph without personal data."""

    help = "Export a privacy-filtered RDF graph for semantic web development."

    def add_arguments(self, parser):
        """Register export path and serialization format options."""
        parser.add_argument(
            "--output",
            default="semantic/exports/station-recharge.ttl",
            help="Destination file for the RDF export.",
        )
        parser.add_argument(
            "--format",
            default="turtle",
            choices=["json-ld", "nt", "turtle", "ttl", "xml"],
            help="RDF serialization format.",
        )

    def handle(self, *args, **options):
        """Build, serialize, and write the RDF graph."""
        try:
            graph = build_semantic_graph()
            payload = serialize_semantic_graph(graph, options["format"])
        except SemanticGraphUnavailable as exc:
            raise CommandError(str(exc)) from exc

        output = Path(options["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")

        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {len(graph)} RDF triples to {output.as_posix()}."
            )
        )
