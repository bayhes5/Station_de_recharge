from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from api.permissions import IsStaffUser
from api.services.semantic_graph import (
    SemanticGraphUnavailable,
    build_semantic_network,
    build_semantic_graph,
    serialize_semantic_graph,
)


READ_ONLY_FORBIDDEN_KEYWORDS = {
    "ADD",
    "CLEAR",
    "COPY",
    "CREATE",
    "DELETE",
    "DROP",
    "INSERT",
    "LOAD",
    "MOVE",
}


@api_view(["GET"])
@permission_classes([IsStaffUser])
def semantic_graph(request):
    """Expose the privacy-filtered RDF graph for development and demos."""
    if not settings.SEMANTIC_DEV_ENDPOINTS_ENABLED:
        return Response({"detail": "Semantic development endpoints are disabled."}, status=404)

    output_format = request.query_params.get("format", "turtle")
    try:
        graph = build_semantic_graph()
        payload = serialize_semantic_graph(graph, output_format)
    except SemanticGraphUnavailable as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    content_type = {
        "json-ld": "application/ld+json",
        "nt": "application/n-triples",
        "xml": "application/rdf+xml",
    }.get(output_format, "text/turtle")
    return HttpResponse(payload, content_type=f"{content_type}; charset=utf-8")


@api_view(["POST"])
@permission_classes([IsStaffUser])
def semantic_sparql(request):
    """Run a read-only SPARQL query against the generated development graph."""
    if not settings.SEMANTIC_DEV_ENDPOINTS_ENABLED:
        return Response({"detail": "Semantic development endpoints are disabled."}, status=404)

    query = str(request.data.get("query", "")).strip()
    if not query:
        return Response({"detail": "The SPARQL query is required."}, status=400)
    if _contains_forbidden_update_keyword(query):
        return Response({"detail": "Only read-only SPARQL queries are allowed."}, status=400)

    try:
        graph = build_semantic_graph()
        result = graph.query(query)
    except SemanticGraphUnavailable as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as exc:  # pragma: no cover - rdflib parser errors vary by version.
        return Response({"detail": f"Invalid SPARQL query: {exc}"}, status=400)

    if result.type == "ASK":
        return Response({"boolean": bool(result)})
    if result.type != "SELECT":
        return Response({"detail": "Only SELECT and ASK queries are exposed by this endpoint."}, status=400)

    variables = [str(variable) for variable in result.vars]
    rows = []
    for row in result:
        rows.append(
            {
                variable: _sparql_value(row[index])
                for index, variable in enumerate(variables)
            }
        )
    return Response({"head": {"vars": variables}, "results": rows})


@api_view(["GET"])
@permission_classes([IsStaffUser])
def semantic_network(request):
    """Expose a compact graph model for frontend visualization."""
    if not settings.SEMANTIC_DEV_ENDPOINTS_ENABLED:
        return Response({"detail": "Semantic development endpoints are disabled."}, status=404)

    return Response(build_semantic_network())


def _contains_forbidden_update_keyword(query):
    normalized = query.upper()
    return any(f" {keyword} " in f" {normalized} " for keyword in READ_ONLY_FORBIDDEN_KEYWORDS)


def _sparql_value(value):
    if value is None:
        return None
    return {
        "value": str(value),
        "type": value.__class__.__name__,
    }
