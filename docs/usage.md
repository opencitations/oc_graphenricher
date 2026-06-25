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
from oc_graphenricher.storage import single_file_storage

storage = single_file_storage(
    graph_path="enriched.json",
    provenance_path="provenance.json",
)
enricher = GraphEnricher(
    g_set=graph_set,
    storage=storage,
)
enricher.enrich()
```

`enrich()` writes the enriched graph and provenance to the configured storage.

With the default `zip_output=True`, `graph_path="enriched.json"` writes `enriched.zip` containing `enriched.json`, and `provenance_path="provenance.json"` writes `provenance.zip` containing `provenance.json`.

To use the OCDM directory layout, pass a storage object:

```python
from oc_graphenricher.enricher import GraphEnricher
from oc_graphenricher.storage import directory_storage

storage = directory_storage(
    output_dir="output",
    supplier_prefix="060",
    items_per_directory=10000,
    items_per_file=1000,
    output_format="json-ld",
    zip_output=True,
)

GraphEnricher(g_set=graph_set, storage=storage).enrich()
```

This writes graph files and provenance files under the same output root. Provenance is placed in the `prov` subdirectories created by `oc_ocdm`.

With the values above, entities whose numeric identifier is up to `10000` are stored under the first directory bucket, and files group up to `1000` entities. For example, a bibliographic resource with an IRI such as `https://w3id.org/oc/meta/br/1` is written to:

```text
output/
└── br/
    └── 060/
        └── 10000/
            ├── 1000.zip
            └── 1000/
                └── prov/
                    └── se.zip
```

`supplier_prefix` controls the supplier directory used for entities whose IRI does not already contain one. If the IRI already contains a supplier prefix, `oc_ocdm` uses the prefix from the IRI. If `supplier_prefix` is omitted, the storage uses `_`.

`items_per_directory` controls the directory bucket size. With `10000`, resources numbered from 1 to 10000 go under `10000`, resources from 10001 to 20000 go under `20000`, and so on. `items_per_file` controls the file bucket size inside that directory. With `1000`, resources numbered from 1 to 1000 go in `1000.zip`, resources from 1001 to 2000 go in `2000.zip`, and so on. Provenance uses the same buckets as the entity it describes and is written below the entity file bucket in `prov/`.

`output_format` applies to both graph and provenance. By default, storage writes JSON-LD and zips the output.

Optional switches allow disabling selected external sources:

```python
enricher = GraphEnricher(
    g_set=graph_set,
    storage=storage,
    use_wikidata=False,
    use_viaf=False,
    use_orcid=False,
)
```

## Instance matching

After enrichment, run `InstanceMatching` to merge duplicate entities.

```python
from oc_graphenricher.instancematching import InstanceMatching
from oc_graphenricher.storage import single_file_storage

storage = single_file_storage(
    graph_path="matched.json",
    provenance_path="provenance.json",
)
matcher = InstanceMatching(
    g_set=graph_set,
    storage=storage,
)
matched_graph_set = matcher.match()
```

The same storage object can be used for instance matching:

```python
from oc_graphenricher.instancematching import InstanceMatching
from oc_graphenricher.storage import directory_storage

storage = directory_storage(output_dir="output")
matched_graph_set = InstanceMatching(g_set=graph_set, storage=storage).match()
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
