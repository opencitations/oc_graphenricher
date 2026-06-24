<!--
SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>

SPDX-License-Identifier: ISC
-->

# Usage

OC GraphEnricher accepts a `GraphSet` as input. The graph set can be created from RDF data with `oc_ocdm`.

```python
from oc_ocdm.graph.graph_set import GraphSet
from oc_ocdm.reader import Reader
from rdflib import Graph

graph = Graph().parse("data/input.nt", format="nt11")

reader = Reader()
graph_set = GraphSet(base_iri="https://w3id.org/oc/meta/")
reader.import_entities_from_graph(
    graph_set,
    graph,
    enable_validation=False,
    resp_agent="https://w3id.org/oc/meta/prov/pa/2",
)
```

If new entities need persistent counters, configure `info_dir` on the `GraphSet` itself:

```python
graph_set = GraphSet(base_iri="https://w3id.org/oc/meta/", info_dir="info")
```

The `info_dir` arguments of `GraphEnricher` and `InstanceMatching` are used for the provenance sets they create.

## Enrichment

Use `GraphEnricher` to add missing identifiers to the graph set.

```python
from oc_graphenricher.enricher import GraphEnricher

enricher = GraphEnricher(
    graph_set,
    graph_filename="enriched.rdf",
    provenance_filename="provenance.rdf",
)
enricher.enrich()
```

`enrich()` writes the enriched graph to `graph_filename` and writes provenance to `provenance_filename`.

Optional switches allow disabling selected external sources:

```python
enricher = GraphEnricher(
    graph_set,
    use_wikidata=False,
    use_viaf=False,
    use_orcid=False,
)
```

## Instance matching

After enrichment, run `InstanceMatching` to merge duplicate entities.

```python
from oc_graphenricher.instancematching import InstanceMatching

matcher = InstanceMatching(
    graph_set,
    graph_filename="matched.rdf",
    provenance_filename="provenance.rdf",
)
matched_graph_set = matcher.match()
```

`match()` runs these steps in order:

1. Responsible agent matching. It matches only responsible agents that share the same identifier scheme and literal. It merges each connected cluster and updates agent-role references to point to the kept responsible agent.
2. Bibliographic resource matching. It matches only bibliographic resources that share the same identifier scheme and literal. After two BRs are merged, it also updates data attached to those BRs:
   - it compares the `is_part_of` chains of the two BRs and merges container BRs from those chains when their RDF types overlap after excluding the generic expression type;
   - if both BRs have a publisher role, it merges the two publisher `AgentRole` objects;
   - among the contributors of the merged BR, it removes duplicated contributor roles. Roles pointing to the same responsible agent are merged. Among the remaining roles, roles with the same non-empty author name are merged.
3. Identifier matching. It finds identifier entities attached to bibliographic resources or responsible agents that share the same scheme and literal, merges them and rewrites entity references to the kept identifier.
4. Serialization. It writes the matched graph and provenance to the configured output files.

The name check is local to the contributors of a BR that has already been merged by identifier. It does not start a responsible-agent match and it does not compare BR titles. In the current implementation, the check uses raw Levenshtein distance, so only identical non-empty author names pass.
