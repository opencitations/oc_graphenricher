<!--
SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>

SPDX-License-Identifier: ISC
-->

# Installation

OC GraphEnricher supports Python `>=3.10,<3.14`.

## Install from PyPI

```bash
pip install oc-graphenricher
```

## Install from source

Clone the repository and install the project dependencies with `uv`:

```bash
git clone https://github.com/opencitations/oc_graphenricher
cd oc_graphenricher
uv sync
```

## Run tests

From the repository root:

```bash
uv run pytest
```
