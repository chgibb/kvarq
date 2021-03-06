
.. highlight:: bash

.. _installing:

Installing KvarQ
================

.. _precompiled:

Precompiled packages
--------------------

The different releases are available als compiled packages for Microsoft
Windows and OSX (10.6 and later): http://github.com/kvarq/kvarq/releases

Note that the packages are currently **not signed** and you therefore
have to `enable OS X to run programs from unidentified developers
<http://www.mcvsd.org/tips/powerteacher/osx_unidentified_developers.html>`_
if you run OS X 10.8 or newer.


.. _install-from-source:

Installing KvarQ From Source
----------------------------

The source code is hosted in a git repository at http://github.com/kvarq/kvarq

.. _dependencies:

Dependencies
~~~~~~~~~~~~

KvarQ does not have any external dependencies, apart from
Sphinx_ for building the html documentation from the ``docs/*.rst``
sources files.


.. _install-from-source-linux:

Linux
~~~~~

in case your system runs a python older than version **2.7**, you have
to install a newer version of python first; this is easiest done
locally

.. code-block:: bash

    wget http://www.python.org/ftp/python/2.7.4/Python-2.7.4.tgz
    tar xzf Python-2.7.4.tgz
    cd Python-2.7.4
    mkdir $HOME/py
    ./configure --prefix=$HOME/py
    make && make install
    PATH=$HOME/py/bin:$PATH
    export $PATH
    python -V

then download and install `setuptools <https://pypi.python.org/pypi/setuptools>`_::

    wget https://bitbucket.org/pypa/setuptools/raw/bootstrap/ez_setup.py -O - | python

download the latest source distribution and build (calling ``setup.py``
with ``test`` will also copy the compiled library into the source
directory)

.. code-block:: bash

    wget https://github.com/kvarq/kvarq/archive/master.zip
    unzip master.zip
    rm master.zip
    cd kvarq-master
    python setup.py test

now you can **either install** KvarQ (optionally into a virtual environment)::

    python setup.py install

**or setup an alias** after including KvarQ into your ``PYTHONPATH``.  This is
the method of choice if you intend to plan :ref:`to modify the KvarQ source
<hacking>` because you don't need to make a fresh installation after every
change -- but don't forget to re-run ``python setup.py test`` in case you changed
the C source code to make sure the compiled extension is copied into the correct
directory (or by sourcing the script ``. ./activate``)

.. code-block:: bash

    PYTHONPATH=`pwd`; export PYTHONPATH
    alias kvarq='python -m kvarq.cli'
    kvarq -h

In either way, you now have the KvarQ command at your disposal and can
continue :ref:`using the commandline <using-cli>` or start the
:ref:`graphical user interface <gui>`.


.. _install-from-source-osx:

OS X
~~~~

Prerequisites:

  - If you use OS X Snow Leopard (10.6) or below, you first have to install
    `Python 2.7 <http://www.python.org/download/releases/2.7/>`_ (this version
    of python is included in OS X Lion 10.7 and newer; but you might
    nevertheless want to install a vanilla copy of Python)

  - On the other hand, OS X Snow Leopard and older include a C compiler that is
    needed to build the program. If you have no C compiler installed (you get a
    ``command not found`` error when you type ``gcc`` or ``clang`` at the
    Terminal), you need to `download Xcode
    <https://developer.apple.com/downloads/index.action>`_ from Apple's
    developer page (registering an account only takes some minutes). Choose
    **Command Line Tools for Xcode** from the "Developer Tools" category.

From this point on, follow the steps outlined in the :ref:`Linux section
<install-from-source-linux>`.  If you want to create an OS X application, you
will also need to download and install `py2app
<http://pythonhosted.org/py2app/>`_.


.. _install-from-source-windows:

Windows
~~~~~~~

Prerequisites:

  - First `download <http://www.python.org/download/releases/2.7.5/>`_ and
    install Python (at least version 2.7). You should download the **32bit**
    version regardless of your machine architecture (or you will `run into
    problems <http://bugs.python.org/issue7511>`_ with the steps outlined
    below).  If you plan to use python for scientific ends, you might want to
    install `the Enthought Canopy Distribution
    <http://www.engthought.com/downloads/>`_ that bundles many interesting
    packages.

  - Because KvarQ uses a compiled module to scan through the files you will
    have to install a C compiler. The simplest choice is to download and
    install Microsoft Visual Studio Express (e.g. `VS Express 2012
    <http://www.microsoft.com/visualstudio/deu/downloads#d-2012-express>`_).
    This will automatically set the environment variable ``VSxx0COMNTOOLS``
    (with ``xx`` being the version of visual studio).

  - KvarQ includes a `pthreads <http://sourceware.org/pthreads-win32/>`_ in
    ``win32/pthreads`` for compiling the C extension.  You have to **copy**
    this file into your windows folder or make sure that ``win32/pthreads``
    is in your DLL search path.

You should now be able to download, build and test the program pretty much the
same way as :ref:`described above <install-from-source-linux>`. To create a
stand-alone executable package (via ``python setup.py py2exe``) you will also
need to `download py2exe <http://www.py2exe.org/>`_.  Finally, you will
probably want to `install some packaging system
<https://zignar.net/2012/06/17/install-python-on-windows/>`_ (not installed by
default) to get more python packages.

