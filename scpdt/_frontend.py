""" Copy-pasting my way through python/cpython/Lib/doctest.py. """

import sys
import os
import inspect
import doctest

from ._impl import DTFinder, DTRunner, DebugDTRunner, DTParser, DTConfig
from ._util import (matplotlib_make_nongui as mpl,
                    temp_cwd, rndm_state, np_errstate,
                    get_public_objects, _map_verbosity)


def find_doctests(module, strategy=None,
                  # doctest parameters. These fall through to the DocTestFinder
                  name=None, exclude_empty=True, globs=None, extraglobs=None,
                  # our configuration
                  config=None):
    """Find doctests in a module.

    Parameters
    ----------
    m : module
        The base module to look into
    strategy : str or list of objects, optional
        The strategy to use to find doctests.
        If "public", look into public, non-deprecated objects in the module.
        If a list of objects, only look into the docstring of these objects
        If None, use the standard `doctest` behavior.
        Default is None.
    name : str, optional
        The name of the module. Is used to construct the names of DocTest
        objects. Default is the `module.__name__`.
    exclude_empty : bool, optional
        Comes from the stdlib `doctest` module. See Notes.
        Default is True.
    globs : dict, optional
        Comes from the stdlib `doctest` module. See Notes.
        Default is None.
    extraglobs : dict, optional
        Comes from the stdlib `doctest` module. See Notes.
        Default is None.
    config
        A `DTConfig` instance

    Returns
    -------
    tests : list
        A list of `doctest.DocTest`s that are defined by the module docstring,
        and by its contained objects’ docstrings. The selection is controlled
        by the `strategy` argument. 

    Notes
    -----
    See https://docs.python.org/3/library/doctest.html#doctestfinder-objects
    for details on the `doctest`-inherited parameters (`name`, `globs`,
    `extraglobs`). Note that these are provided mainly for compatibility with
    the stdlib `doctest` and can be left with default values unless you are
    doing something unusual.

    """
    if config is None:
        config = DTConfig()

    finder = DTFinder(exclude_empty=exclude_empty, config=config)

    if strategy is None:
        tests = finder.find(module, name, globs=globs, extraglobs=extraglobs)
        return tests

    if strategy == "api":
        (items, names), failures = get_public_objects(module,
                                                      skiplist=config.skiplist)
        # XXX: handle failures
    else:
        # strategy must then be a list of objects to look at
        if not isinstance(strategy, list):
            raise ValueError(f"Expected a list of objects, got {strategy}.")
        items = strategy[:]
        names = [item.__name__ for item in items]

    tests = []
    for item, name in zip(items, names):
        if inspect.ismodule(item):
            # do not recurse, only inspect the module docstring
            _finder = DTFinder(recurse=False, config=config)
            t = _finder.find(item, name, globs=globs, extraglobs=extraglobs)
        else:
            t = finder.find(item, name, globs=globs, extraglobs=extraglobs)
        tests += t

    return tests



def testmod(m=None, name=None, globs=None, verbose=None,
            report=True, optionflags=None, extraglobs=None,
            raise_on_error=False, exclude_empty=True,
            strategy=None, config=None):
    """Run modified doctesting on a module or on docstrings of a list of objects.

    This function is an analog of the `testmod` driver from the standard library.

    Parameters
    ----------
    m : module, optional
        Test examples in docstrings in functions and classes reachable
        from module `m` (or the current module if `m` is not supplied),
        starting with ``m.__doc__``.
    name : str, optional
        Gives the name of the module; by default use ``m.__name__``.
    globs : dict, optional
        A dict to be used as the globals when executing examples;  A copy of this
        dict is actually used for each docstring, so that each docstring's
        examples start with a clean slate.
        By default, use `config.default_namespace`.
    report : bool, optional
        Prints a summary at the end when `True`, else prints nothing at the end.
        In verbose mode, the summary is detailed, else very brief (in fact,
        empty if all tests passed)
        Default is True.
   verbose : int
        Control the run verbosity:
        0 means only report failures,
        1 means emit object names,
        2 is the max verbosity from doctest (print all examples/want/got).
        Default is 0.
    optionflags : int, optional
        `doctest` module optionflags for checking examples. See the stdlib
        `doctest` module documentation for details.
        Default is to use `config.optionflags`.
    extraglobs : dict, optional
        Provided for compatibility with `doctest.testmod`. Default is None.
    raise_on_error : bool, optional
        Raise an exception on the first unexpected exception or failure.
        This allows failures to be post-mortem debugged.
        Default is `False`.
    exclude_empty : bool, optional
        Whether to exclude from consideration objects with no docstrings.
        Comes from the stdlib `doctest` module. See Notes.
        Default is True.
    strategy : str or list of objects, optional
        The strategy to use to find doctests.
        If "api", look into public, non-deprecated objects in the module.
        If a list of objects, only look into the docstring of these objects
        If None, use the standard `doctest` behavior.
        Default is None.
    config : a DTConfig instance, optional
        Various configuration options. See the `DTconfig` docstring for details.

    Returns
    -------
    (result, history)
        `result` is a namedtuple ``TestResult(failed, attempted)``
        `history` is a dict with details of which objects were examined (the
        keys are object names and values are individual objects' ``TestResult``s)

    Examples
    --------
    >>> from scipy import constants
    >>> from scpdt import testmod
    >>> result, history = testmod(constants, strategy='api')
    >>> result
    TestResults(failed=0, attempted=25)
    >>> len(history)
    160

    Notes
    -----
    The signature is made to be (mostly) consistent with `doctest.testmod`.
    For details on the `doctest`-inherited parameters see 
    https://docs.python.org/3/library/doctest.html.
    For an overview, see ``help(doctest)``.

    ** Doctest discovery **

    The default doctest discovery strategy, `testmod(..., strategy=None)`, is
    inherited from the stdlib `doctest` module with all its limitations.
    For instance, it may have difficulties with complex packages, where the
    implementation is spread across several modules. 

    For complex packages, prefer `strategy='api'`, which works as follows:
    - take the names of public objects from the `__all__` attribute of the package.
    - if `__all__` is not defined, take `dir(module)` and filter out names
      which start with a leading underscore and dunders.
    - filter out deprecated items, i.e. those which raise `DeprecationWarning`.

    """
    ### mimic `doctest.testmod` initial set-ups
    # If no module was given, then use __main__.
    if m is None:
        m = sys.modules.get('__main__')

    # Check that we were actually given a module.
    if not inspect.ismodule(m):
        raise TypeError("testmod: module required; %r" % (m,))

    # If no name was given, then use the module's name.
    if name is None:
        name = m.__name__

    ### Set up the configuration
    if config is None:
        config = DTConfig()

    # pull the the namespace to run examples in, also optionflags from `config`
    if globs is None:
        globs = dict(config.default_namespace)
    flags = config.optionflags

    output = sys.stderr

    # Fail fast or run all tests
    verbose, dtverbose = _map_verbosity(verbose)
    if raise_on_error:
        runner = DebugDTRunner(verbose=dtverbose, optionflags=flags, config=config)
    else:
        runner = DTRunner(verbose=dtverbose, optionflags=flags, config=config)

    ### Find, parse, and run all tests in the given module.
    tests = find_doctests(m, strategy, name, exclude_empty, globs, extraglobs, config=config)

    for test in tests:
        if verbose == 1:
            output.write(test.name + '\n')
        # restore (i) the errstate/print state, and (ii) np.random state
        # after each docstring. Also make MPL backend non-GUI and close
        # the figures.
        # The order of context managers is actually relevant. Consider
        # a user_context_mgr that turns warnings into errors.
        # Additionally, suppose that MPL deprecates something and plt.something
        # starts issuing warngings. Now all of those become errors
        # *unless* the `mpl()` context mgr has a chance to filter them out
        # *before* they become errors in `config.user_context_mgr()`.
        with np_errstate():
            with rndm_state():
                with config.user_context_mgr():
                    with mpl(), temp_cwd():
                        runner.run(test, out=output.write)
    if report:
        runner.summarize()
    return doctest.TestResults(runner.failures, runner.tries), runner.get_history()


def testfile(filename, module_relative=True, name=None, package=None,
             globs=None, verbose=None, report=True, optionflags=None,
             extraglobs=None, raise_on_error=False, parser=None,
             encoding=None, config=None):

    # config
    if config is None:
        config = DTConfig()
    if globs is None:
        globs = dict(config.default_namespace)     
    if optionflags is None:
        optionflags = config.optionflags
    flags = optionflags

    if extraglobs is not None:
        raise NotImplementedError()
    ## XXX also extraglobs, package etc

    if parser is None:
        parser = DTParser(config)

    ### mimic `doctest.tesfile` initial set-ups
    # If no name was given, then use the file's name.
##    if name is None:
##        name = os.path.basename(filename)

    output = sys.stderr

    # Fail fast or run all tests
    verbose, dtverbose = _map_verbosity(verbose)
    if raise_on_error:
        runner = DebugDTRunner(verbose=dtverbose, optionflags=flags, config=config)
    else:
        runner = DTRunner(verbose=dtverbose, optionflags=flags, config=config)

    ### Read the file, convert it to a test, and run it.
    with open(filename, encoding='utf-8') as f:
        text = f.read()

    name = os.path.basename(filename)

    test = parser.get_doctest(text, globs, name, filename, 0)

    if verbose == 1:
        output.write(test.name + '\n')
    # restore (i) the errstate/print state, and (ii) np.random state
    # after each docstring. Also make MPL backend non-GUI and close
    # the figures.
    # The order of context managers is actually relevant. Consider
    # a user_context_mgr that turns warnings into errors.
    # Additionally, suppose that MPL deprecates something and plt.something
    # starts issuing warngings. Now all of those become errors
    # *unless* the `mpl()` context mgr has a chance to filter them out
    # *before* they become errors in `config.user_context_mgr()`.
    with np_errstate():
        with rndm_state():
            with config.user_context_mgr():
                with mpl(), temp_cwd():
                    runner.run(test, out=output.write)
    if report:
        runner.summarize()
    return doctest.TestResults(runner.failures, runner.tries), runner.get_history()


def run_docstring_examples(f, globs=None, verbose=False, name='NoName',
                           optionflags=None, config=None):
    """Run examples in the docstring of the object `f`.

    Parameters
    ----------
    f
        Can be a function, a class, a module etc
    globs : dict, optional
        A dict to be used as the globals when executing examples;  A copy of this
        dict is actually used for each docstring, so that each docstring's
        examples start with a clean slate.
        By default, use `config.default_namespace`.
    verbose : bool, optional
        Control the verbosity of the report.
    name : str, optional
        The object name.
    optionflags : int, optional
        `doctest` module optionflags for checking examples. See the stdlib
        `doctest` module documentation for details.
        Default is to use `config.optionflags`.
    config : a DTConfig instance, optional
        Various configuration options. See the `DTconfig` docstring for details.
    """
    if config is None:
        config = DTConfig()
    if globs is None:
        globs = dict(config.default_namespace)
    if verbose is None:
        verbose = 0
    if optionflags is None:
        optionflags = config.optionflags
    
    m = f.__module__
    import importlib
    module = importlib.import_module(m)

    return testmod(module, name=name, globs=globs, verbose=verbose,
                   optionflags=optionflags, strategy=[f], config=config)


def _main():
    """CLI for `$ python -m scpdt pythonfile.py`, cf `__main__.py`
    """
    import argparse

    parser = argparse.ArgumentParser(description="doctest runner")
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='print verbose (`-v`) or very verbose (`-vv`) '
                              'output for all tests')
    parser.add_argument('-x', '--fail-fast', action='store_true',
                        help=('stop running tests after first failure'))
    parser.add_argument('file', nargs='+',
                        help='file containing the tests to run')
    args = parser.parse_args()
    testfiles = args.file
    verbose = args.verbose

    for filename in testfiles:
        if filename.endswith(".py"):
            # It is a module -- insert its dir into sys.path and try to
            # import it. If it is part of a package, that possibly
            # won't work because of package imports.
            dirname, filename = os.path.split(filename)
            sys.path.insert(0, dirname)
            m = __import__(filename[:-3])
            del sys.path[0]
            result, _ = testmod(m, verbose=verbose,
                                  raise_on_error=args.fail_fast)
        else:
            # XXX: UNTESTED, LIKELY BROKEN
            failures, _ = testfile(filename, module_relative=False,
                                     verbose=verbose, optionflags=options)

        if result.failed:
            return 1
    return 0

