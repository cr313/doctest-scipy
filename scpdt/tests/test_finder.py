import pytest

from . import finder_cases
from ..util import get_all_list, get_public_objects
from ..impl import DTFinder, DTConfig
from ..frontend import find_doctests

def test_get_all_list():
    items, depr, other = get_all_list(finder_cases)
    assert sorted(items) == ['Klass', 'func']


def test_get_all_list_no_all():
    # test get_all_list on a module which does not define all.
    # Remove __all__, test, reload on exit to not depend on the test order.
    try:
        del finder_cases.__all__
        items, depr, other = get_all_list(finder_cases)
        assert items == []
    finally:
        from importlib import reload
        reload(finder_cases)


def test_get_objects():
    (items, names), failures = get_public_objects(finder_cases)
    assert items == [finder_cases.func, finder_cases.Klass]
    assert names == [obj.__name__ for obj in items]
    assert failures == []


def test_get_objects_extra_items():
    # test get_all_list on a module which defines an incorrect all.
    # Patch __all__, test, reload on exit to not depend on the test order.
    try:
        finder_cases.__all__ += ['spurious']
        (items, names), failures = get_public_objects(finder_cases)

        assert items == [finder_cases.func, finder_cases.Klass]
        assert len(failures) == 1

        failed = failures[0]
        assert failed[0].endswith(".spurious")
        assert failed[2].startswith("Missing item")

    finally:
        from importlib import reload
        reload(finder_cases)


def test_find_doctests_extra_items():
    # test find_doctests on a module which defines an incorrect all.
    # Patch __all__, test, reload on exit to not depend on the test order.
    try:
        finder_cases.__all__ += ['spurious', 'missing']
        with pytest.raises(ValueError):
            find_doctests(finder_cases, strategy='api')
    finally:
        from importlib import reload
        reload(finder_cases)


class TestSkiplist:
    """Test skipping items via skiplists."""
    def test_get_objects_skiplist(self):
        skips = [finder_cases.__name__ + '.' + 'func']
        (items, name), failures = get_public_objects(finder_cases, skiplist=skips)

        assert items == [finder_cases.Klass]
        assert failures == []

    def test_get_doctests_no_skiplist(self):
        # strategy=None is equivalent to vanilla doctest module: finds all objects
        tests = find_doctests(finder_cases)
        names = [t.name for t in tests]

        wanted_names = ['Klass', 'Klass.meth', 'Klass.meth_2', 'func',
                        'private_func', '_underscored_private_func']
        base = finder_cases.__name__
        wanted_names = [base] + [base + '.' + n for n in wanted_names]

        assert sorted(names) == sorted(wanted_names)

    def test_get_doctests_strategy_None(self):
        # Add a skiplist: strategy=None skips listed items 
        base = finder_cases.__name__  
        skips = [base + '.func', base + '.Klass.meth_2']
        config = DTConfig(skiplist=skips)

        tests = find_doctests(finder_cases, config=config)
        names = [t.name for t in tests]

        # note the lack of `func` and `Klass.meth_2`, as requested
        wanted_names = ['Klass', 'Klass.meth',
                        'private_func', '_underscored_private_func']
        wanted_names = [base] + [base + '.' + n for n in wanted_names]

        assert sorted(names) == sorted(wanted_names)

    def test_get_doctests_strategy_api(self):
        # Add a skiplist: strategy='api' skips listed items 
        base = finder_cases.__name__  
        skips = [base + '.func', base + '.Klass.meth_2']
        config = DTConfig(skiplist=skips)

        tests = find_doctests(finder_cases, strategy='api', config=config)
        names = [t.name for t in tests]

        # note the lack of
        #   - `func` and `Klass.meth_2`, as requested (via the skiplist)
        #   - *private* stuff, which is not in `__all__`
        wanted_names = ['Klass', 'Klass.meth']
        wanted_names = [base] + [base + '.' + n for n in wanted_names]

        assert sorted(names) == sorted(wanted_names)

    def test_get_doctests_strategy_list(self):
        # Add a skiplist: strategy=<list> skips listed items 
        base = finder_cases.__name__  
        skips = [base + '.func', base + '.Klass.meth_2']
        config = DTConfig(skiplist=skips)

        tests = find_doctests(finder_cases,
                              strategy=[finder_cases.Klass], config=config)
        names = [t.name for t in tests]

        # note the lack of
        #   - `Klass.meth_2`, as requested (via the skiplist)
        #   - the 'base' module (via the strategy=<list>)
        wanted_names = ['Klass', 'Klass.meth']
        wanted_names = [base + '.' + n for n in wanted_names]

        assert sorted(names) == sorted(wanted_names)


def test_explicit_object_list():
    objs = [finder_cases.Klass]
    tests = find_doctests(finder_cases, strategy=objs)

    base = 'scpdt.tests.finder_cases'
    assert ([test.name for test in tests] ==
            [base + '.Klass', base + '.Klass.meth', base + '.Klass.meth_2'])


def test_explicit_object_list_with_module():
    # Module docstrings are examined literally, without looking into other objects
    # in the module. These other objects need to be listed explicitly.
    # In the `doctest`-speak: do not recurse.
    objs = [finder_cases, finder_cases.Klass]
    tests = find_doctests(finder_cases, strategy=objs)

    base = 'scpdt.tests.finder_cases'
    assert ([test.name for test in tests] ==
            [base, base + '.Klass', base + '.Klass.meth', base + '.Klass.meth_2'])


def test_find_doctests_api():
    # Test that the module itself is included with strategy='api'
    tests = find_doctests(finder_cases, strategy='api')

    base = 'scpdt.tests.finder_cases'
    assert ([test.name for test in tests] ==
            [base + '.func', base + '.Klass', base + '.Klass.meth',
             base + '.Klass.meth_2', base])


def test_dtfinder_config():
    config = DTConfig()
    finder = DTFinder(config=config)
    assert finder.config is config
