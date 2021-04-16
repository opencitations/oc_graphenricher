How to install
==================

Installing from Pypi
########

To get the official and updated version of this package, follow these simple steps:

1. install python >= 3.8:

    .. code-block:: console

        sudo apt install python3

2. Install oc_graphenricher via pip:

    .. code-block:: console

        pip install oc-graphenricher


Installing from the sources
########
It's also possible to build the package from the sources. To do that, follow the following:

1. Having already installed python, you can also install GraphEnricher via cloning this repository:

    .. code-block:: bash

        git clone https://github.com/opencitations/oc_graphenricher`
        cd ./oc_graphenricher

2. install poetry:

    .. code-block:: bash

        pip install poetry

3. install all the dependencies:

    .. code-block:: bash

        poetry install

4. build the package:

    .. code-block:: bash

        poetry build

5. install the package:

    .. code-block:: bash

        pip install ./dist/oc_graphenricher-<VERSION>.tar.gz

Run the tests
########
To run the tests (from the root of the project):

    .. code-block:: bash

        poetry run test
