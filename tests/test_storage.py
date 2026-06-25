# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from pathlib import Path

from oc_ocdm.graph.graph_set import GraphSet
from oc_ocdm.prov.prov_set import ProvSet

from oc_graphenricher._storage import store_graph_set, store_provenance
from oc_graphenricher.storage import directory_storage
from tests.helpers import BASE_IRI, RESP_AGENT


def test_directory_storage_writes_graph_and_provenance_to_ocdm_layout(tmp_path: Path) -> None:
    graph_set, provenance = _graph_set_with_provenance()

    output_dir = tmp_path / "ocdm"
    storage = directory_storage(output_dir, supplier_prefix="060", output_format="nt11", zip_output=False)

    store_graph_set(graph_set, storage)
    store_provenance(provenance, storage)

    rdf_files = sorted(
        path.relative_to(output_dir).as_posix() for path in output_dir.rglob("*") if path.suffix in {".nq", ".nt"}
    )
    assert rdf_files == [
        "br/060/10000/1000.nt",
        "br/060/10000/1000/prov/se.nq",
    ]


def test_directory_storage_defaults_to_zipped_jsonld(tmp_path: Path) -> None:
    graph_set, provenance = _graph_set_with_provenance()

    output_dir = tmp_path / "ocdm"
    storage = directory_storage(output_dir, supplier_prefix="060")

    store_graph_set(graph_set, storage)
    store_provenance(provenance, storage)

    zip_files = sorted(
        path.relative_to(output_dir).as_posix() for path in output_dir.rglob("*") if path.suffix == ".zip"
    )
    assert zip_files == [
        "br/060/10000/1000.zip",
        "br/060/10000/1000/prov/se.zip",
    ]


def _graph_set_with_provenance() -> tuple[GraphSet, ProvSet]:
    graph_set = GraphSet(BASE_IRI)
    br = graph_set.add_br(RESP_AGENT)
    br.create_journal_article()
    br.has_title("Directory storage test")
    graph_set.commit_changes()

    provenance = ProvSet(graph_set, graph_set.base_iri)
    provenance.generate_provenance(c_time=0)
    return graph_set, provenance
