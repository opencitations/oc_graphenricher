# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from pathlib import Path

import pytest
from oc_ocdm.graph.graph_set import GraphSet

from oc_graphenricher.instancematching import InstanceMatching
from tests.helpers import load_graph_set

TEST_DATA_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def matched_graph_set(tmp_path: Path) -> GraphSet:
    matcher = InstanceMatching(
        load_graph_set(TEST_DATA_DIR / "test_merge_br.rdf"),
        graph_filename=str(tmp_path / "matched.rdf"),
        provenance_filename=str(tmp_path / "provenance.rdf"),
        debug=True,
    )
    matcher.match()
    return load_graph_set(tmp_path / "matched.rdf")
