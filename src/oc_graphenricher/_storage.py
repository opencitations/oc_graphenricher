# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from __future__ import annotations

import os
from typing import TYPE_CHECKING, cast

from oc_ocdm.storer import Storer

from oc_graphenricher.storage import DirectoryStorage, Storage

if TYPE_CHECKING:
    from oc_ocdm.abstract_entity import AbstractEntity
    from oc_ocdm.abstract_set import AbstractSet
    from oc_ocdm.graph.graph_set import GraphSet
    from oc_ocdm.prov.prov_set import ProvSet


def store_graph_set(graph_set: GraphSet, storage: Storage) -> None:
    storer = _storer(cast("AbstractSet[AbstractEntity]", graph_set), storage)
    if isinstance(storage, DirectoryStorage):
        storer.store_all(
            _directory_output(storage.output_dir),
            graph_set.base_iri,
            storage.context_path,
            process_id=storage.process_id,
        )
    else:
        storer.store_graphs_in_file(storage.graph_path, storage.context_path)


def store_provenance(provenance: ProvSet, storage: Storage) -> None:
    storer = _storer(cast("AbstractSet[AbstractEntity]", provenance), storage)
    if isinstance(storage, DirectoryStorage):
        storer.store_all(
            _directory_output(storage.output_dir),
            provenance.base_iri,
            storage.context_path,
            process_id=storage.process_id,
        )
    else:
        storer.store_graphs_in_file(storage.provenance_path, storage.context_path)


def _storer(entity_set: AbstractSet[AbstractEntity], storage: Storage) -> Storer:
    if isinstance(storage, DirectoryStorage):
        return Storer(
            entity_set,
            repok=storage.repok,
            reperr=storage.reperr,
            context_map=storage.context_map,
            default_dir=storage.supplier_prefix,
            dir_split=storage.items_per_directory,
            n_file_item=storage.items_per_file,
            output_format=storage.output_format,
            zip_output=storage.zip_output,
            modified_entities=storage.modified_entities,
        )
    return Storer(
        entity_set,
        repok=storage.repok,
        reperr=storage.reperr,
        context_map=storage.context_map,
        output_format=storage.output_format,
        zip_output=storage.zip_output,
        modified_entities=storage.modified_entities,
    )


def _directory_output(directory: str) -> str:
    if directory.endswith(os.sep):
        return directory
    return directory + os.sep
