Installing
==================

Installing from Pypi
########

To get a local copy up and running follow these simple steps:

1. install python >= 3.8:
.. code-block:: console
    sudo apt install python3

2. Install oc_graphenricher via pip:
.. code-block:: console
    pip install oc-graphenricher


Installing from the sources
########

1. Having already installed python, you can also install GraphEnricher via cloning this repository:
.. code-block:: console
    git clone https://github.com/opencitations/oc_graphenricher`
    cd ./oc_graphenricher

2. install poetry:
.. code-block:: console
    pip install poetry

3. install all the dependencies:
.. code-block:: console
    poetry install

4. build the package:
.. code-block:: console
    poetry build

5. install the package:
.. code-block:: console
    pip install ./dist/oc_graphenricher-<VERSION>.tar.gz

Run the tests
########
To run the tests (from the root of the project):
.. code-block:: console
    poetry run test
