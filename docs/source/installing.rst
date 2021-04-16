Installing
########

To get a local copy up and running follow these simple steps:

1. install python >= 3.8:

.. code-block::
    sudo apt install python3

2. Install oc_graphenricher via pip:

.. code-block::
    pip install oc-graphenricher


Installing from the sources
########

1. Having already installed python, you can also install GraphEnricher via cloning this repository:

.. code-block::
    git clone https://github.com/opencitations/oc_graphenricher`
    cd ./oc_graphenricher

2. install poetry:

.. code-block::
    pip install poetry

3. install all the dependencies:

.. code-block::
    poetry install

4. build the package:

.. code-block::
    poetry build

5. install the package:

.. code-block:: pip install ./dist/oc_graphenricher-<VERSION>.tar.gz

Run the tests
########
To run the tests (from the root of the project):

.. code-block::
    poetry run test
