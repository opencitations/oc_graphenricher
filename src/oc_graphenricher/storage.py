# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from __future__ import annotations

from dataclasses import dataclass
from os import PathLike, fspath
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from oc_ocdm._types import ContextMap
    from oc_ocdm.counter_handler import CounterHandler
    from oc_ocdm.support.reporter import Reporter

PathInput: TypeAlias = str | PathLike[str]


@dataclass(frozen=True, slots=True)
class SingleFileStorage:
    graph_path: str
    provenance_path: str
    output_format: str = "json-ld"
    zip_output: bool = True
    repok: Reporter | None = None
    reperr: Reporter | None = None
    context_map: ContextMap | None = None
    context_path: str | None = None
    modified_entities: set[str] | None = None
    supplier_prefix: str = ""
    info_dir: str | None = ""
    wanted_label: bool = True
    counter_handler: CounterHandler | None = None


@dataclass(frozen=True, slots=True)
class DirectoryStorage:
    output_dir: str
    items_per_directory: int = 10000
    items_per_file: int = 1000
    supplier_prefix: str = "_"
    output_format: str = "json-ld"
    zip_output: bool = True
    repok: Reporter | None = None
    reperr: Reporter | None = None
    context_map: ContextMap | None = None
    context_path: str | None = None
    modified_entities: set[str] | None = None
    process_id: int | str | None = None
    info_dir: str | None = ""
    wanted_label: bool = True
    counter_handler: CounterHandler | None = None


Storage: TypeAlias = SingleFileStorage | DirectoryStorage


def single_file_storage(
    graph_path: PathInput,
    provenance_path: PathInput,
    *,
    output_format: str = "json-ld",
    zip_output: bool = True,
    repok: Reporter | None = None,
    reperr: Reporter | None = None,
    context_map: ContextMap | None = None,
    context_path: str | None = None,
    modified_entities: set[str] | None = None,
    supplier_prefix: str = "",
    info_dir: str | None = "",
    wanted_label: bool = True,
    counter_handler: CounterHandler | None = None,
) -> SingleFileStorage:
    return SingleFileStorage(
        graph_path=fspath(graph_path),
        provenance_path=fspath(provenance_path),
        output_format=output_format,
        zip_output=zip_output,
        repok=repok,
        reperr=reperr,
        context_map=context_map,
        context_path=context_path,
        modified_entities=modified_entities,
        supplier_prefix=supplier_prefix,
        info_dir=info_dir,
        wanted_label=wanted_label,
        counter_handler=counter_handler,
    )


def directory_storage(
    output_dir: PathInput,
    *,
    items_per_directory: int = 10000,
    items_per_file: int = 1000,
    supplier_prefix: str = "_",
    output_format: str = "json-ld",
    zip_output: bool = True,
    repok: Reporter | None = None,
    reperr: Reporter | None = None,
    context_map: ContextMap | None = None,
    context_path: str | None = None,
    modified_entities: set[str] | None = None,
    process_id: int | str | None = None,
    info_dir: str | None = "",
    wanted_label: bool = True,
    counter_handler: CounterHandler | None = None,
) -> DirectoryStorage:
    if items_per_directory < 0:
        message = "items_per_directory must be greater than or equal to 0."
        raise ValueError(message)
    if items_per_file <= 0:
        message = "items_per_file must be greater than 0."
        raise ValueError(message)
    output_dir_path = fspath(output_dir)
    if output_dir_path == "":
        message = "output_dir cannot be empty."
        raise ValueError(message)
    return DirectoryStorage(
        output_dir=output_dir_path,
        items_per_directory=items_per_directory,
        items_per_file=items_per_file,
        supplier_prefix=supplier_prefix,
        output_format=output_format,
        zip_output=zip_output,
        repok=repok,
        reperr=reperr,
        context_map=context_map,
        context_path=context_path,
        modified_entities=modified_entities,
        process_id=process_id,
        info_dir=info_dir,
        wanted_label=wanted_label,
        counter_handler=counter_handler,
    )


__all__ = [
    "Storage",
    "directory_storage",
    "single_file_storage",
]
