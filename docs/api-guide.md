<!--
SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>

SPDX-License-Identifier: ISC
-->

# API guide

This page documents the classes normally used by applications that integrate OC GraphEnricher.

## `GraphEnricher`

Import from `oc_graphenricher.enricher`.

```python
from oc_graphenricher.enricher import GraphEnricher
```

`GraphEnricher` enriches an OCDM graph set by adding missing identifiers.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `g_set` | required | Input `GraphSet` to enrich. |
| `graph_filename` | `"enriched.rdf"` | RDF output path for the enriched graph. |
| `provenance_filename` | `"provenance.rdf"` | RDF output path for provenance. |
| `info_dir` | `""` | Counter directory passed to the provenance set created by the enricher. New identifiers use the counter handler of the input `GraphSet`. |
| `debug` | `False` | Enables debug logging. |
| `serialize_in_the_middle` | `False` | Serializes the graph every 50 bibliographic resources. |
| `use_wikidata` | `True` | Enables Wikidata queries. |
| `use_viaf` | `True` | Enables VIAF queries. |
| `use_orcid` | `True` | Enables ORCID queries. |

The main method is `enrich()`. It processes bibliographic resources, skips journal issues and journal volumes, enriches related responsible agents and serializes graph and provenance outputs.

For bibliographic resources, enrichment can add ISSN, DOI, Wikidata and OpenAlex identifiers. For responsible agents, enrichment can add ORCID, VIAF, Wikidata and Crossref publisher identifiers.

## `InstanceMatching`

Import from `oc_graphenricher.instancematching`.

```python
from oc_graphenricher.instancematching import InstanceMatching
```

`InstanceMatching` deduplicates entities in an OCDM graph set.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `g_set` | required | Input `GraphSet` to deduplicate. |
| `graph_filename` | `"matched.rdf"` | RDF output path for the matched graph. |
| `provenance_filename` | `"provenance.rdf"` | RDF output path for provenance. |
| `info_dir` | `""` | Counter directory passed to the provenance set used during matching. |
| `debug` | `False` | Enables debug logging. |

Use `match()` to run all matching steps and save the result. It returns the updated `GraphSet`.

Matching candidates are selected by identifier equality. Name comparison is used only while cleaning contributors on a bibliographic resource that has already been merged by identifier.

In this context, a container is a bibliographic resource reached through the `is_part_of` chain of a matched BR, such as a parent issue, volume, journal or other parent BR represented in the input graph. Container merge is scoped to the two `is_part_of` chains of the BRs being merged.

The individual methods are available when a workflow needs one matching phase at a time:

| Method | Action |
| --- | --- |
| `instance_matching_ra()` | Builds clusters of responsible agents that share the same identifier scheme and literal, merges each cluster into one responsible agent and rewrites agent-role references to the kept entity. It does not compare names. |
| `instance_matching_br()` | Builds clusters of bibliographic resources that share the same identifier scheme and literal. For each merged BR cluster, it also handles linked data: it may merge BRs in the two `is_part_of` chains when their RDF types overlap, merge publisher `AgentRole` objects attached to the merged BRs and remove duplicated contributor `AgentRole` objects on the resulting BR. The contributor cleanup first merges roles pointing to the same responsible agent, then merges remaining roles with identical non-empty author names. |
| `instance_matching_id()` | Merges identifier entities that share the same scheme and literal, then replaces references from bibliographic resources and responsible agents with the kept identifier. |
| `save()` | Serializes the graph set and provenance. |
