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

For provenance counters created by `GraphEnricher` and `GraphDeduplicator`, pass `info_dir` to the storage factory.

## Enrichment

Use `GraphEnricher` to add missing identifiers to the graph set.

```python
from oc_graphenricher.enricher import GraphEnricher
from oc_graphenricher.storage import single_file_storage

storage = single_file_storage(
    graph_path="enriched.json",
    provenance_path="provenance.json",
    info_dir="info",
)
enricher = GraphEnricher(
    graph_set=graph_set,
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

GraphEnricher(graph_set=graph_set, storage=storage).enrich()
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

The storage object also carries the provenance settings used when `GraphEnricher` or `GraphDeduplicator` saves
provenance. Use `supplier_prefix`, `info_dir`, `wanted_label` and `counter_handler` on the storage factory when those
values are needed by `ProvSet`.

Optional switches allow disabling selected external sources:

```python
enricher = GraphEnricher(
    graph_set=graph_set,
    storage=storage,
    use_wikidata=False,
    use_viaf=False,
    use_orcid=False,
)
```

Use `checkpoint_interval` to write the graph after a fixed number of processed bibliographic resources:

```python
enricher = GraphEnricher(
    graph_set=graph_set,
    storage=storage,
    checkpoint_interval=50,
)
```

## Deduplication

After enrichment, run `GraphDeduplicator` to merge duplicate entities.

```python
from oc_graphenricher.deduplication import GraphDeduplicator
from oc_graphenricher.storage import single_file_storage

storage = single_file_storage(
    graph_path="deduplicated.json",
    provenance_path="provenance.json",
)
deduplicator = GraphDeduplicator(
    graph_set=graph_set,
    storage=storage,
)
deduplicated_graph_set = deduplicator.deduplicate_and_save()
```

Use `deduplicate()` when the caller needs to manage serialization separately:

```python
deduplicator = GraphDeduplicator(graph_set=graph_set)
deduplicated_graph_set = deduplicator.deduplicate()
```

The same storage object can be used for deduplication:

```python
from oc_graphenricher.deduplication import GraphDeduplicator
from oc_graphenricher.storage import directory_storage

storage = directory_storage(output_dir="output")
deduplicated_graph_set = GraphDeduplicator(graph_set=graph_set, storage=storage).deduplicate_and_save()
```

`deduplicate()` runs these steps in order:

1. Responsible agent deduplication. It merges only responsible agents that share the same identifier scheme and literal. It merges each connected cluster and updates agent-role references to point to the kept responsible agent.
2. Bibliographic resource deduplication. It merges only bibliographic resources that share the same identifier scheme and literal. After two BRs are merged, it also updates data attached to those BRs:
   - it compares the `is_part_of` chains of the two BRs and merges paired container BRs of the same type walking the hierarchy from the top down. A container pair is merged only when the two containers are equivalent: they share an identifier, or (when identity cannot be decided by identifiers) they have the same sequence number, or the same title. Containers with conflicting identifiers, different numbers or different titles are kept distinct, and a level is merged only if its parent level was also merged;
   - if both BRs have a publisher role, it merges the two publisher `AgentRole` objects;
   - among the contributors of the merged BR, it removes duplicated contributor roles. Roles with the same role type pointing to the same responsible agent are merged. Name-based contributor merging is disabled by default and can be enabled with `merge_similar_named_contributors=True`.
3. Identifier deduplication. It finds identifier entities attached to bibliographic resources or responsible agents that share the same scheme and literal, merges them and rewrites entity references to the kept identifier.

Responsible agent and bibliographic resource merges keep functional values already present on the surviving entity. Missing survivor values can still be filled from merged entities. For responsible agents this applies to `name`, `given_name` and `family_name`. For bibliographic resources this applies to `title`, `subtitle`, `is_part_of`, `pub_date`, `number` and `edition`.

`deduplicate_and_save()` calls `deduplicate()` and then writes the deduplicated graph and provenance to the configured
output files. Calling `deduplicate_and_save()` or `save()` without storage raises `ValueError`.

The name check is local to the contributors of a BR that has already been merged by identifier. It does not start responsible-agent deduplication and it does not compare BR titles.

`GraphDeduplicator` rewrites references inside the supplied `GraphSet`. If the graph set is only a slice of a larger dataset, references outside that slice are not rewritten automatically. Callers should load the entities that can refer to the resources being merged, including containers, publishers and agent roles that may be affected by BR merges.

Use `preferred_survivors` when a caller must preserve selected entity URIs:

```python
deduplicated_graph_set = GraphDeduplicator(
    graph_set=graph_set,
    storage=storage,
    preferred_survivors={"https://w3id.org/oc/meta/br/0602"},
).deduplicate_and_save()
```

The set contains entity URIs that must be kept if they appear in duplicate clusters. If exactly one preferred URI appears
in a cluster, deduplication keeps it. If multiple preferred URIs appear in the same cluster, deduplication raises
`ValueError`. If none appears, deduplication keeps the entity with more functional metadata. Ties use URI order.

Use `merge_clusters()` when another application has already selected the merge clusters:

```python
deduplicator = GraphDeduplicator(graph_set=graph_set)
deduplicator.merge_clusters(
    {
        "https://w3id.org/oc/meta/ra/0601": [
            "https://w3id.org/oc/meta/ra/0602",
            "https://w3id.org/oc/meta/ra/0603",
        ],
    }
)
```

`merge_clusters()` uses the mapping keys as surviving entity URIs and merges only the values listed for each key. It
does not discover additional duplicate clusters. Use `merge_clusters_and_save()` to run the same caller-provided merge
and then write the graph and provenance through the configured storage.

Manual clusters can contain responsible agents, bibliographic resources or identifiers, but each cluster must contain only one entity type. Identifier clusters are accepted only when every merged identifier has the same scheme and literal as the survivor. Otherwise `merge_clusters()` raises `ValueError` before changing the graph.

For provenance generated during deduplication, use the same storage options used for enrichment.
