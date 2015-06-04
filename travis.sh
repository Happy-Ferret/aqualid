set -ex

coverage run --source=aql tests/run.py

python -c "import aql;import sys;sys.exit(aql.main())" -C make -l
python -c "import aql;import sys;sys.exit(aql.main())" -C make -L c++

git clone --depth 1 https://github.com/aqualid/tools.git

PYTHONPATH=$PWD python tools/tests/run.py

python -c "import aql;import sys;sys.exit(aql.main())" -C make local sdist -I $PWD/tools/tools

python -c "import aql;import sys;sys.exit(aql.main())" -C make local sdist -I $PWD/tools/tools --use-sqlite
python -c "import aql;import sys;sys.exit(aql.main())" -C make local sdist -I $PWD/tools/tools -R --force-lock


git clone --depth 1 https://github.com/aqualid/examples.git

python -c "import aql;import sys;sys.exit(aql.main())" -C examples/cpp_hello -I $PWD/tools/tools
python -c "import aql;import sys;sys.exit(aql.main())" -C examples/cpp_hello -I $PWD/tools/tools -R
python -c "import aql;import sys;sys.exit(aql.main())" -C examples/cpp_generator -I $PWD/tools/tools
python -c "import aql;import sys;sys.exit(aql.main())" -C examples/cpp_generator -I $PWD/tools/tools -R
python -c "import aql;import sys;sys.exit(aql.main())" -C examples/cpp_libs -I $PWD/tools/tools
python -c "import aql;import sys;sys.exit(aql.main())" -C examples/cpp_libs_1 -I $PWD/tools/tools
python -c "import aql;import sys;sys.exit(aql.main())" -C examples/cpp_libs_2 -I $PWD/tools/tools
python -c "import aql;import sys;sys.exit(aql.main())" -C examples/cpp_libs_2 -I $PWD/tools/tools -R

flake8 --max-complexity=9 `find aql -name "[a-zA-Z]*.py"`
flake8 `find tests -name "[a-zA-Z]*.py"`
flake8 make/*.py
pep8 make/make.aql
