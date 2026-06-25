# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from pathlib import Path

import pytest
from oc_ocdm.graph.graph_set import GraphSet

from oc_graphenricher.instancematching import InstanceMatching
from oc_graphenricher.storage import single_file_storage
from tests.helpers import load_graph_set

TEST_DATA_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def matched_graph_set(tmp_path: Path) -> GraphSet:
    matcher = InstanceMatching(
        load_graph_set(TEST_DATA_DIR / "test_merge_br.rdf"),
        single_file_storage(
            tmp_path / "matched.rdf",
            tmp_path / "provenance.rdf",
            output_format="nt11",
            zip_output=False,
        ),
        debug=True,
    )
    matcher.match()
    return load_graph_set(tmp_path / "matched.rdf")
