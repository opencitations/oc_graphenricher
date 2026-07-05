<!--
SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
SPDX-FileCopyrightText: 2021 Silvio Peroni <silvio.peroni@unibo.it>
SPDX-FileCopyrightText: 2023 Arianna Moretti <arianna.moretti4@unibo.it>
SPDX-FileCopyrightText: 2024 Elia Rizzetto <elia.rizzetto@studio.unibo.it>
SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>

SPDX-License-Identifier: ISC
-->

[![Tests](https://github.com/opencitations/oc_graphenricher/actions/workflows/test.yml/badge.svg)](https://github.com/opencitations/oc_graphenricher/actions/workflows/test.yml)
[![Pyright](https://github.com/opencitations/oc_graphenricher/actions/workflows/pyright.yml/badge.svg)](https://github.com/opencitations/oc_graphenricher/actions/workflows/pyright.yml)
[![Ruff](https://github.com/opencitations/oc_graphenricher/actions/workflows/ruff.yml/badge.svg)](https://github.com/opencitations/oc_graphenricher/actions/workflows/ruff.yml)
[![Coverage](https://opencitations.github.io/oc_graphenricher/coverage/coverage-badge.svg)](https://opencitations.github.io/oc_graphenricher/coverage/)
[![REUSE status](https://api.reuse.software/badge/github.com/opencitations/oc_graphenricher)](https://api.reuse.software/info/github.com/opencitations/oc_graphenricher)

# OC GraphEnricher

OC GraphEnricher enriches [OpenCitations Data Model (OCDM)](https://doi.org/10.6084/m9.figshare.3443876) compliant knowledge graphs by finding missing identifiers and deduplicating entities.

Documentation: <https://opencitations.github.io/oc_graphenricher/>

## Quick start

```bash
pip install oc-graphenricher
```

```python
from oc_ocdm.graph.graph_set import GraphSet
from oc_ocdm.reader import Reader
from rdflib import Graph

from oc_graphenricher.enricher import GraphEnricher
from oc_graphenricher.deduplication import GraphDeduplicator
from oc_graphenricher.storage import single_file_storage

graph = Graph().parse("data/input.nt", format="nt11")

reader = Reader()
graph_set = GraphSet(base_iri="https://w3id.org/oc/meta/")
reader.import_entities_from_graph(
    graph_set,
    graph,
    enable_validation=False,
    resp_agent="https://w3id.org/oc/meta/prov/pa/2",
)

GraphEnricher(
    graph_set=graph_set,
    storage=single_file_storage(
        graph_path="enriched.json",
        provenance_path="provenance.json",
    ),
).enrich()
GraphDeduplicator(
    graph_set=graph_set,
    storage=single_file_storage(
        graph_path="deduplicated.json",
        provenance_path="provenance.json",
    ),
).deduplicate_and_save()
```

By default, `GraphDeduplicator` does not merge contributor roles only because author names are similar. To enable that
opt-in behavior, pass `merge_similar_named_contributors=True`.

Use `deduplicate()` instead of `deduplicate_and_save()` when another application needs to manage storage or provenance
output itself.
Use `preferred_survivors` with a set of entity URIs to keep selected entities when duplicate clusters are merged.
Without a preferred survivor, duplicate clusters keep the entity with more functional metadata. Ties use URI order.
Use `merge_clusters()` when another application has already selected the merge clusters, for example from a reviewed
CSV. The mapping key is the surviving entity URI and the values are the URIs to merge into it. This method does not
discover or merge any extra duplicates outside the provided mapping.

For configuration options and usage details, see the documentation.

## License

Distributed under the ISC License. See [LICENSE](LICENSE).
