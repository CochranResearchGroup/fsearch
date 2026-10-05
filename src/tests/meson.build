test_array = executable('test_array', 'test_array.c', dependencies: libfsearch_dep)
test_query = executable('test_query', 'test_query.c', dependencies: libfsearch_dep)
test_size_utils = executable('test_size_utils', 'test_size_utils.c', dependencies: libfsearch_dep)
test_string_utils = executable('test_string_utils', 'test_string_utils.c', dependencies: libfsearch_dep)
test_time_utils = executable('test_time_utils', 'test_time_utils.c', dependencies: libfsearch_dep)
test_database_entry = executable('test_database_entry', 'test_database_entry.c', dependencies: libfsearch_dep)
test_database_include = executable('test_database_include', 'test_database_include.c', dependencies : libfsearch_dep)
test_database_exclude = executable('test_database_exclude', 'test_database_exclude.c', dependencies : libfsearch_dep)
test_database_chunked_array = executable('test_database_chunked_array', 'test_database_chunked_array.c', dependencies : libfsearch_dep)
test_database_index_store = executable('test_database_index_store', 'test_database_index_store.c', dependencies : libfsearch_dep)
test_database = executable('test_database', 'test_database.c', dependencies : libfsearch_dep)
test_database_file = executable('test_database_file', 'test_database_file.c', dependencies : libfsearch_dep)

test('test_database',
     test_database,
     env : [
         'G_TEST_SRCDIR=@0@'.format(meson.current_source_dir()),
         'G_TEST_BUILDDIR=@0@'.format(meson.current_build_dir()),
     ],
     timeout : 60,
)
test('test_database_file',
     test_database_file,
     env : [
         'G_TEST_SRCDIR=@0@'.format(meson.current_source_dir()),
         'G_TEST_BUILDDIR=@0@'.format(meson.current_build_dir()),
     ],
)
test('test_database_chunked_array',
     test_database_chunked_array,
     env : [
         'G_TEST_SRCDIR=@0@'.format(meson.current_source_dir()),
         'G_TEST_BUILDDIR=@0@'.format(meson.current_build_dir()),
     ],
)
test('test_database_index_store',
     test_database_index_store,
     env : [
         'G_TEST_SRCDIR=@0@'.format(meson.current_source_dir()),
         'G_TEST_BUILDDIR=@0@'.format(meson.current_build_dir()),
     ],
)
test('test_database_include',
     test_database_include,
     env : [
         'G_TEST_SRCDIR=@0@'.format(meson.current_source_dir()),
         'G_TEST_BUILDDIR=@0@'.format(meson.current_build_dir()),
     ],
)
test('test_database_exclude',
     test_database_exclude,
     env : [
         'G_TEST_SRCDIR=@0@'.format(meson.current_source_dir()),
         'G_TEST_BUILDDIR=@0@'.format(meson.current_build_dir()),
     ],
)
test('test_database_entry',
     test_database_entry,
     env : [
         'G_TEST_SRCDIR=@0@'.format(meson.current_source_dir()),
         'G_TEST_BUILDDIR=@0@'.format(meson.current_build_dir()),
     ],
)
test('test_array',
     test_array,
     env: [
       'G_TEST_SRCDIR=@0@'.format(meson.current_source_dir()),
       'G_TEST_BUILDDIR=@0@'.format(meson.current_build_dir()),
     ],
)
test('test_query',
     test_query,
     env: [
       'G_TEST_SRCDIR=@0@'.format(meson.current_source_dir()),
       'G_TEST_BUILDDIR=@0@'.format(meson.current_build_dir()),
     ],
)
test('test_size_utils',
     test_size_utils,
     env: [
       'G_TEST_SRCDIR=@0@'.format(meson.current_source_dir()),
       'G_TEST_BUILDDIR=@0@'.format(meson.current_build_dir()),
     ],
)
test('test_string_utils',
     test_string_utils,
     env: [
       'G_TEST_SRCDIR=@0@'.format(meson.current_source_dir()),
       'G_TEST_BUILDDIR=@0@'.format(meson.current_build_dir()),
     ],
)
test('test_time_utils',
     test_time_utils,
     env: [
       'G_TEST_SRCDIR=@0@'.format(meson.current_source_dir()),
       'G_TEST_BUILDDIR=@0@'.format(meson.current_build_dir()),
     ],
)

if host_machine.system() == 'linux'
    snapshot_fixture = executable('snapshot_fixture', 'snapshot_fixture.c', dependencies: libfsearch_dep)
    headless_fault_fixture = shared_library('headless_fault_fixture', 'headless_fault_fixture.c',
        dependencies: cc.find_library('dl'), install: false)
    python = find_program('python3')
    refresh_fault_fixture = shared_library('refresh_fault_fixture', 'refresh_fault_fixture.c', dependencies: cc.find_library('dl'), install: false)
    monitor_fault_fixture = shared_library('monitor_fault_fixture', 'monitor_fault_fixture.c', dependencies: cc.find_library('dl'), install: false)
    test('monitor_supervisor', python, args: [files('test_monitor.py'), fsearch_monitor, fsearch_cli.full_path(), meson.current_build_dir()],
        depends: [fsearch_monitor_worker, fsearch_refresh_worker, fsearch_worker, fsearch_cli, refresh_fault_fixture, headless_fault_fixture, monitor_fault_fixture], timeout: 30)
    test('approved_root_move_race', python, args: [files('../prototypes/verify_root_move_race.py'),
        '--runtime', join_paths(meson.current_build_dir(), '..'), '--fault', refresh_fault_fixture.full_path(),
        '--evidence-dir', join_paths(meson.current_build_dir(), 'move-race-evidence')],
        depends: [fsearch_monitor_worker, fsearch_refresh_worker, refresh_fault_fixture], timeout: 30)
    test('monitor_worker', python, args: [files('test_monitor_worker.py'), fsearch_monitor_worker.full_path(), monitor_fault_fixture.full_path(), refresh_fault_fixture.full_path()],
        depends: [fsearch_monitor_worker, monitor_fault_fixture, refresh_fault_fixture], timeout: 30)
    test('refresh_worker', python, args: [files('test_refresh.py'), fsearch_refresh_worker.full_path(), fsearch_cli.full_path(), refresh_fault_fixture.full_path(), headless_fault_fixture.full_path()],
        depends: [fsearch_refresh_worker, fsearch_cli, refresh_fault_fixture, headless_fault_fixture], timeout: 30)
    test('warm_service', python, args: [files('test_service.py'), fsearch_service, fsearch_cli.full_path(), snapshot_fixture.full_path(), headless_fault_fixture.full_path()],
        depends: [fsearch_worker, fsearch_cli, fsearch_refresh_worker, refresh_fault_fixture, snapshot_fixture, headless_fault_fixture], timeout: 60)
    test('headless_cli', python,
        args: [files('test_headless.py'), fsearch_cli.full_path(), snapshot_fixture.full_path(), headless_fault_fixture.full_path()],
        depends: [fsearch_cli, snapshot_fixture, headless_fault_fixture], timeout: 60)
endif
