import app.core.database as database


def test_database_discovery_does_not_assume_external_runtime(isolated_database):
    result = database.initialize()
    assert result['status'] == 'initialized'
    assert database.discover_database_path().exists()
    assert '/Volumes/HGRJ5880J/' not in result['database_path']


def test_incompatible_existing_schema_is_blocked_without_migration(tmp_path, monkeypatch):
    import sqlite3
    bad_path = tmp_path / 'legacy.sqlite3'
    with sqlite3.connect(bad_path) as con:
        con.execute('CREATE TABLE settings (id INTEGER PRIMARY KEY, payload TEXT)')
    monkeypatch.setattr(database, 'discover_database_path', lambda: bad_path)
    try:
        database.initialize()
    except RuntimeError as exc:
        assert 'schema_incompatible' in str(exc)
    else:
        raise AssertionError('incompatible database schema was silently accepted')
    with sqlite3.connect(bad_path) as con:
        cols = {row[1] for row in con.execute('PRAGMA table_info(settings)')}
    assert cols == {'id', 'payload'}


def test_preflight_recognizes_writable_ancestor_when_data_directory_is_missing(tmp_path, monkeypatch):
    import app.core.database as database
    candidate = tmp_path / 'not-created-yet' / 'nested' / 'julian.sqlite3'
    monkeypatch.setattr(database, 'discover_database_path', lambda: candidate)
    result = database.preflight_database_path()
    assert result['status'] == 'ready_for_review'
    assert result['database_exists'] is False
    assert result['database_parent_exists'] is False
    assert result['nearest_existing_parent'] == str(tmp_path)
    assert result['nearest_existing_parent_writable'] is True
    assert not candidate.parent.exists()
