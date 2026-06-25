# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from oc_ocdm.storer import Storer

if TYPE_CHECKING:
    from oc_ocdm.abstract_entity import AbstractEntity
    from oc_ocdm.abstract_set import AbstractSet
    from oc_ocdm.graph.graph_set import GraphSet
    from oc_ocdm.prov.prov_set import ProvSet


def store_graph_set(graph_set: GraphSet, graph_filename: str) -> None:
    storer = Storer(cast("AbstractSet[AbstractEntity]", graph_set), output_format="nt11")
    storer.store_graphs_in_file(graph_filename, "")


def store_provenance(provenance: ProvSet, provenance_filename: str) -> None:
    storer = Storer(cast("AbstractSet[AbstractEntity]", provenance), output_format="nquads")
    storer.store_graphs_in_file(provenance_filename, "")
