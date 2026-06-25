<!--
SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>

SPDX-License-Identifier: ISC
-->

# OC GraphEnricher

OC GraphEnricher enriches [OpenCitations Data Model (OCDM)](https://doi.org/10.6084/m9.figshare.3443876) compliant knowledge graphs by finding missing identifiers and deduplicating entities.

The package works with `GraphSet` objects from `oc_ocdm`. The current package metadata does not expose a command-line interface, so usage starts from Python code.

## Components

`GraphEnricher` adds identifiers to bibliographic resources and responsible agents. It can query Crossref, ORCID, VIAF, Wikidata and OpenAlex.

`InstanceMatching` deduplicates responsible agents, bibliographic resources and identifiers that share identifier data.

## Identifiers

OC GraphEnricher can add these identifiers when the related external source returns a match:

| Entity | Identifiers |
| --- | --- |
| Bibliographic resource | DOI, ISSN, Wikidata ID, OpenAlex Work ID, OpenAlex Source ID |
| Responsible agent | ORCID, VIAF, Wikidata ID, Crossref publisher ID |

## Start here

Use the [installation guide](installing.md) to install the package, then follow the [usage guide](usage.md) to create a graph set, enrich it and run instance matching.
