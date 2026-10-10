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
    test('boot_recovery', python, args: files('test_boot_recovery.py'), timeout: 10)
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

if host_machine.system() == 'linux'
    test_catalog = executable('test_catalog', 'test_catalog.c', dependencies: libfsearch_dep)
    test('immutable_catalog', test_catalog, timeout: 60)
endif
if host_machine.system() == 'linux'
    test_catalog_faults = executable('test_catalog_faults', 'test_catalog_faults.c', dependencies: libfsearch_dep)
    test('immutable_catalog_faults', test_catalog_faults, timeout: 30)
endif
if host_machine.system() == 'linux'
    catalog_oracle_worker = executable('catalog_oracle_worker', '../fsearch_worker.c', c_args: ['-DFSEARCH_WORKER_ORACLE'], dependencies: libfsearch_dep)
    catalog_fixture = executable('catalog_fixture', 'catalog_fixture.c', dependencies: libfsearch_dep)
    test('catalog_native_parity', python, args: [files('test_catalog_parity.py'), catalog_fixture.full_path(), snapshot_fixture.full_path(), catalog_oracle_worker.full_path()],
        depends: [catalog_fixture, snapshot_fixture, catalog_oracle_worker], timeout: 60)
endif
if host_machine.system() == 'linux'
    test('pressure_guard_controls', python, args: [files('test_pressure_guard.py'), files('run_pressure_guard.py')], timeout: 15)
endif
if host_machine.system() == 'linux'
    test('catalog_worker_transport', python, args: [files('test_catalog_transport.py'), fsearch_service, snapshot_fixture.full_path()],
        depends: [fsearch_worker, snapshot_fixture], timeout: 30)
endif

if host_machine.system() == 'linux'
    test('catalog_multiroot', python, args: [files('test_catalog_multiroot.py'), snapshot_fixture.full_path(), fsearch_worker.full_path(), catalog_oracle_worker.full_path()],
        depends: [snapshot_fixture, fsearch_worker, catalog_oracle_worker], timeout: 30)
endif
if host_machine.system() == 'linux'
    catalog_query_benchmark = executable('catalog_query_benchmark', 'catalog_query_benchmark.c', dependencies: libfsearch_dep)
endif
if host_machine.system() == 'linux'
    test('continuous_events', python, args: [files('test_continuous_events.py'), fsearch_monitor_worker.full_path(), monitor_fault_fixture.full_path()],
        depends: [fsearch_monitor_worker, monitor_fault_fixture], timeout: 30)
endif
if host_machine.system() == 'linux'
    test('incremental_visibility', python, args: [files('test_incremental.py'), fsearch_service, fsearch_incremental, snapshot_fixture.full_path()],
        depends: [fsearch_monitor_worker, fsearch_refresh_worker, fsearch_worker, snapshot_fixture], timeout: 40)
endif
if host_machine.system() == 'linux'
    test('catalog_journal_boundaries', python, args: files('test_catalog_journal.py'), timeout: 15)
    checkpoint_fault_fixture = shared_library('checkpoint_fault_fixture', 'checkpoint_fault_fixture.c', dependencies: cc.find_library('dl'), install: false)
    test('catalog_durable_capacity', python, args: [files('test_catalog_capacity.py'), join_paths(meson.project_build_root(), 'src')],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 120)
    test('catalog_append_log_fsync_crash', python, args: [files('test_catalog_append_crash.py'), join_paths(meson.project_build_root(), 'src'), 'log_fsync'],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_append_cursor_pre_rename_crash', python, args: [files('test_catalog_append_crash.py'), join_paths(meson.project_build_root(), 'src'), 'cursor_pre_rename'],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_append_cursor_published_crash', python, args: [files('test_catalog_append_crash.py'), join_paths(meson.project_build_root(), 'src'), 'cursor_published'],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_startup_transport_failure', python, args: [files('test_catalog_startup_failure.py'), join_paths(meson.project_build_root(), 'src')],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_startup_transport_protocol', python, args: [files('test_catalog_startup_failure.py'), join_paths(meson.project_build_root(), 'src'), 'protocol'],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_startup_transport_timeout', python, args: [files('test_catalog_startup_failure.py'), join_paths(meson.project_build_root(), 'src'), 'timeout'],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_startup_transport_replay', python, args: [files('test_catalog_startup_failure.py'), join_paths(meson.project_build_root(), 'src'), 'replay'],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_prior_boot_ready', python, args: [files('test_catalog_prior_boot.py'), join_paths(meson.project_build_root(), 'src'), 'ready'],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_prior_boot_starting', python, args: [files('test_catalog_prior_boot.py'), join_paths(meson.project_build_root(), 'src'), 'starting'],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_prior_boot_quarantined', python, args: [files('test_catalog_prior_boot.py'), join_paths(meson.project_build_root(), 'src'), 'quarantined'],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_prior_boot_current_boot', python, args: [files('test_catalog_prior_boot.py'), join_paths(meson.project_build_root(), 'src'), 'current_boot'],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_prior_boot_mixed_boot', python, args: [files('test_catalog_prior_boot.py'), join_paths(meson.project_build_root(), 'src'), 'mixed_boot'],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_crash_manifest_pre_rename', python, args: [files('test_catalog_checkpoint_crash.py'), join_paths(meson.project_build_root(), 'src'), 'manifest_pre_rename'],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_crash_manifest_published', python, args: [files('test_catalog_checkpoint_crash.py'), join_paths(meson.project_build_root(), 'src'), 'manifest_published'],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_crash_checkpoint_write', python, args: [files('test_catalog_checkpoint_crash.py'), join_paths(meson.project_build_root(), 'src'), 'checkpoint_write', checkpoint_fault_fixture.full_path()],
        depends: [fsearch_refresh_worker, fsearch_worker, checkpoint_fault_fixture], timeout: 30)
    test('catalog_corrupt_pair', python, args: [files('test_catalog_corrupt_pair.py'), join_paths(meson.project_build_root(), 'src')],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_corrupt_pair_unavailable', python, args: [files('test_catalog_corrupt_pair.py'), join_paths(meson.project_build_root(), 'src'), 'both'],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_corrupt_pair_binding', python, args: [files('test_catalog_corrupt_pair.py'), join_paths(meson.project_build_root(), 'src'), 'binding'],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_corrupt_pair_sequence', python, args: [files('test_catalog_corrupt_pair.py'), join_paths(meson.project_build_root(), 'src'), 'sequence'],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_corrupt_pair_metadata', python, args: [files('test_catalog_corrupt_pair.py'), join_paths(meson.project_build_root(), 'src'), 'metadata'],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_corrupt_pair_manifest', python, args: [files('test_catalog_corrupt_pair.py'), join_paths(meson.project_build_root(), 'src'), 'manifest'],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 30)
    test('catalog_durable_replacement', python, args: [files('test_catalog_replacement_durability.py'), join_paths(meson.project_build_root(), 'src')],
        depends: [fsearch_refresh_worker, fsearch_worker], timeout: 40)
    test('catalog_durable_rollover', python, args: [files('test_catalog_rollover.py'), join_paths(meson.project_build_root(), 'src'), checkpoint_fault_fixture.full_path()],
        depends: [fsearch_refresh_worker, fsearch_worker, checkpoint_fault_fixture], timeout: 30)
    test('catalog_native_checkpoint', python, args: [files('test_catalog_checkpoint_worker.py'), join_paths(meson.project_build_root(), 'src'), checkpoint_fault_fixture.full_path()],
        depends: [fsearch_refresh_worker, fsearch_worker, checkpoint_fault_fixture], timeout: 30)
    test('catalog_durable_replay', python, args: [files('test_catalog_durability.py'), join_paths(meson.project_build_root(), 'src')],
        depends: [fsearch_refresh_worker, fsearch_worker, fsearch_cli], timeout: 30)
    test('fanotify_event_filter', python, args: files('test_fanotify_events.py'), timeout: 10)
    test('fanotify_owned_coalescing', python, args: files('test_fanotify_coalescing.py'), timeout: 10)
    test('broker_source_transport', python, args: files('test_broker_source.py'), timeout: 10)
    test_broker_listener = executable('test_broker_listener', 'test_broker_listener.c', install: false)
    test('broker_listener_credentials', test_broker_listener, timeout: 10)
    test_broker_mark_descriptor = executable('test_broker_mark_descriptor', 'test_broker_mark_descriptor.c', install: false)
    test('broker_mark_descriptor', test_broker_mark_descriptor, timeout: 10)
    test('broker_directory_map', python, args: files('test_broker_admission.py'), timeout: 10)
    test('broker_permission_exclusions', python, args: [files('test_broker_permission_exclusions.py'), join_paths(meson.project_build_root(), 'src'), broker_boundary.full_path()],
        depends: [broker_boundary, fsearch_refresh_worker, fsearch_worker, fsearch_cli], timeout: 15)
    test('broker_entry_eligibility', python, args: [files('test_broker_entry_eligibility.py'), join_paths(meson.project_build_root(), 'src'), broker_boundary.full_path()],
        depends: [broker_boundary, fsearch_refresh_worker, fsearch_worker, fsearch_cli], timeout: 15)
    test('broker_process_cli_mcp', python, args: [files('test_broker_process.py'), join_paths(meson.project_build_root(), 'src'), '-', broker_boundary.full_path()],
        depends: [broker_boundary, fsearch_refresh_worker, fsearch_worker, fsearch_cli], timeout: 30)
    test('broker_dirty_startup_preserves_accepted', python, args: [files('test_broker_process.py'), join_paths(meson.project_build_root(), 'src'), '-', broker_boundary.full_path(), '--startup-churn'],
        depends: [broker_boundary, fsearch_refresh_worker, fsearch_worker, fsearch_cli], timeout: 30)
    test('broker_permission_startup_cli_mcp', python, args: [files('test_broker_process.py'), join_paths(meson.project_build_root(), 'src'), '-', broker_boundary.full_path(), '--permission-exclusions'],
        depends: [broker_boundary, fsearch_refresh_worker, fsearch_worker, fsearch_cli], timeout: 30)
endif
