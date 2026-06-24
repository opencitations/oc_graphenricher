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

OC GraphEnricher enriches OpenCitations Data Model (OCDM) compliant knowledge graphs by finding missing identifiers and deduplicating entities.

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
from oc_graphenricher.instancematching import InstanceMatching

graph = Graph().parse("data/input.nt", format="nt11")

reader = Reader()
graph_set = GraphSet(base_iri="https://w3id.org/oc/meta/")
reader.import_entities_from_graph(
    graph_set,
    graph,
    enable_validation=False,
    resp_agent="https://w3id.org/oc/meta/prov/pa/2",
)

GraphEnricher(graph_set).enrich()
InstanceMatching(graph_set).match()
```

For configuration options and usage details, see the documentation.

## License

Distributed under the ISC License. See `LICENSE`.
