# -*- coding: utf-8 -*-
"""Plain SQL dump of the Odoo database without pg_dump.

Odoo.sh does not let the database user read pg_settings, and pg_dump stops on that query. This writes the
same kind of file as ``pg_dump --no-owner`` (plain format) from the catalogs the user may read, so the
backup restores in Odoo's database manager or in Odoo.sh like any other dump.sql.

It covers what an Odoo database holds in the public schema: extensions, functions, sequences, tables and
their data (with table inheritance, used by ir_act_*), defaults, constraints, indexes, views, triggers and comments. Anything else (custom types,
partitions, identity or generated columns) stops the dump with an explicit error instead of
producing a backup that would not restore.
"""

SCHEMA = 'public'
HEADER = """--
-- Odoo database dump (SBU, without pg_dump)
--

SET statement_timeout = 0;
SET lock_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;
SET row_security = off;
SELECT pg_catalog.set_config('search_path', '', false);

"""
NOT_EXTENSION = """NOT EXISTS (SELECT 1 FROM pg_catalog.pg_depend dep
                    WHERE dep.classid = '{catalog}'::pg_catalog.regclass AND dep.objid = {oid} AND dep.deptype = 'e')"""


class SqlDumpError(Exception):
    pass


def ident(name):
    return '"' + name.replace('"', '""') + '"'


def qualified(name):
    return f'{ident(SCHEMA)}.{ident(name)}'


def literal(value):
    return "'" + value.replace("'", "''") + "'"


def _not_ext(catalog, oid):
    return NOT_EXTENSION.format(catalog=catalog, oid=oid)


def _check_supported(cr, ns):
    problems = []
    cr.execute(f"""
        SELECT relname, relkind FROM pg_catalog.pg_class c
         WHERE relnamespace = %s AND relkind IN ('p', 'f', 'm') AND {_not_ext('pg_class', 'c.oid')}""", [ns])
    kinds = {'p': 'partitioned table', 'f': 'foreign table', 'm': 'materialized view'}
    problems += [f'{kinds[kind]} {name}' for name, kind in cr.fetchall()]
    cr.execute(f"""
        SELECT t.typname FROM pg_catalog.pg_type t
         WHERE t.typnamespace = %s AND t.typtype IN ('e', 'c', 'd', 'r', 'm')
           AND (t.typrelid = 0 OR (SELECT relkind FROM pg_catalog.pg_class WHERE oid = t.typrelid) = 'c')
           AND {_not_ext('pg_type', 't.oid')}""", [ns])
    problems += [f'type {name}' for (name,) in cr.fetchall()]
    cr.execute("""
        SELECT c.relname || '.' || a.attname FROM pg_catalog.pg_attribute a
          JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
         WHERE c.relnamespace = %s AND c.relkind = 'r' AND a.attnum > 0 AND NOT a.attisdropped
           AND (a.attidentity <> '' OR a.attgenerated <> '')""", [ns])
    problems += [f'identity/generated column {name}' for (name,) in cr.fetchall()]
    cr.execute(f"""
        SELECT proname FROM pg_catalog.pg_proc p
         WHERE pronamespace = %s AND prokind NOT IN ('f', 'p') AND {_not_ext('pg_proc', 'p.oid')}""", [ns])
    problems += [f'aggregate {name}' for (name,) in cr.fetchall()]
    if problems:
        raise SqlDumpError('Not supported by the built-in backup: ' + ', '.join(sorted(problems)))


def _parents_first(cr, tables):
    """Order tables so that a parent of table inheritance is created before its children."""
    cr.execute('SELECT inhrelid, inhparent FROM pg_catalog.pg_inherits')
    parents = {}
    for child, parent in cr.fetchall():
        parents.setdefault(child, set()).add(parent)
    by_oid = {table[0]: table for table in tables}
    ordered, done = [], set()

    def visit(oid):
        if oid in done or oid not in by_oid:
            return
        done.add(oid)
        for parent in sorted(parents.get(oid, ())):
            visit(parent)
        ordered.append(by_oid[oid])

    for table in tables:
        visit(table[0])
    return ordered


def _views_in_dependency_order(cr, ns):
    cr.execute(f"""
        SELECT c.oid, c.relname, pg_catalog.pg_get_viewdef(c.oid) FROM pg_catalog.pg_class c
         WHERE c.relnamespace = %s AND c.relkind = 'v' AND {_not_ext('pg_class', 'c.oid')}
         ORDER BY c.relname""", [ns])
    views = {oid: (name, definition) for oid, name, definition in cr.fetchall()}
    cr.execute("""
        SELECT DISTINCT r.ev_class, dep.refobjid FROM pg_catalog.pg_rewrite r
          JOIN pg_catalog.pg_depend dep ON dep.classid = 'pg_rewrite'::pg_catalog.regclass AND dep.objid = r.oid
         WHERE dep.refclassid = 'pg_class'::pg_catalog.regclass AND dep.refobjid <> r.ev_class
           AND r.ev_class = ANY(%s)""", [list(views)])
    needs = {oid: set() for oid in views}
    for oid, ref in cr.fetchall():
        if ref in views:
            needs[oid].add(ref)
    ordered, done = [], set()

    def visit(oid, path=()):
        if oid in done:
            return
        if oid in path:
            raise SqlDumpError(f'Circular views: {views[oid][0]}')
        for ref in sorted(needs[oid]):
            visit(ref, path + (oid,))
        done.add(oid)
        ordered.append(views[oid])

    for oid in sorted(views, key=lambda o: views[o][0]):
        visit(oid)
    return ordered


def write_sql_dump(cr, out):
    """Write the dump of the database behind ``cr`` into the binary file ``out``.

    Use a dedicated cursor: its transaction (REPEATABLE READ in Odoo) gives one consistent snapshot of all
    tables. Its search_path is emptied during the dump, so every name comes out schema qualified exactly as
    with pg_dump, and set back afterwards.
    """
    def w(text=''):
        out.write(text.encode())

    cr.execute('SHOW search_path')
    search_path = cr.fetchone()[0]
    cr.execute("SET LOCAL search_path = ''")
    try:
        _write(cr, out, w)
    finally:
        cr.execute("SELECT pg_catalog.set_config('search_path', %s, true)", [search_path])


def _write(cr, out, w):
    cr.execute('SELECT oid FROM pg_catalog.pg_namespace WHERE nspname = %s', [SCHEMA])
    ns = cr.fetchone()[0]
    _check_supported(cr, ns)
    w(HEADER)

    cr.execute("""
        SELECT e.extname, n.nspname FROM pg_catalog.pg_extension e
          JOIN pg_catalog.pg_namespace n ON n.oid = e.extnamespace
         WHERE e.extname <> 'plpgsql' ORDER BY e.extname""")
    for name, schema in cr.fetchall():
        w(f'CREATE EXTENSION IF NOT EXISTS {ident(name)} WITH SCHEMA {ident(schema)};\n')
    w('\n')

    cr.execute(f"""
        SELECT pg_catalog.pg_get_functiondef(p.oid) FROM pg_catalog.pg_proc p
         WHERE pronamespace = %s AND prokind IN ('f', 'p') AND {_not_ext('pg_proc', 'p.oid')}
         ORDER BY p.proname, p.oid""", [ns])
    for (definition,) in cr.fetchall():
        w(definition.rstrip().rstrip(';') + ';\n\n')

    cr.execute(f"""
        SELECT c.oid, c.relname, pg_catalog.format_type(s.seqtypid, NULL), s.seqstart, s.seqincrement,
               s.seqmin, s.seqmax, s.seqcache, s.seqcycle
          FROM pg_catalog.pg_sequence s JOIN pg_catalog.pg_class c ON c.oid = s.seqrelid
         WHERE c.relnamespace = %s AND {_not_ext('pg_class', 'c.oid')} ORDER BY c.relname""", [ns])
    sequences = cr.fetchall()
    for _oid, name, typ, start, inc, smin, smax, cache, cycle in sequences:
        w(f'CREATE SEQUENCE {qualified(name)} AS {typ} START WITH {start} INCREMENT BY {inc} '
          f'MINVALUE {smin} MAXVALUE {smax} CACHE {cache}{" CYCLE" if cycle else ""};\n')
    w('\n')

    cr.execute(f"""
        SELECT c.oid, c.relname, c.relpersistence FROM pg_catalog.pg_class c
         WHERE c.relnamespace = %s AND c.relkind = 'r' AND {_not_ext('pg_class', 'c.oid')}
         ORDER BY c.relname""", [ns])
    tables = _parents_first(cr, cr.fetchall())
    columns, inherited_alters = {}, []
    for oid, name, persistence in tables:
        cr.execute("""
            SELECT a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod), a.attnotnull,
                   pg_catalog.pg_get_expr(d.adbin, d.adrelid),
                   CASE WHEN a.attcollation <> t.typcollation THEN co.collname END, a.attislocal
              FROM pg_catalog.pg_attribute a
              JOIN pg_catalog.pg_type t ON t.oid = a.atttypid
         LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
         LEFT JOIN pg_catalog.pg_collation co ON co.oid = a.attcollation
             WHERE a.attrelid = %s AND a.attnum > 0 AND NOT a.attisdropped
             ORDER BY a.attnum""", [oid])
        cols = cr.fetchall()
        columns[oid] = [col[0] for col in cols]
        lines = []
        for col, typ, notnull, default, collation, local in cols:
            if not local:
                # Comes from the parent table; only its own default / NOT NULL is set afterwards.
                if default is not None:
                    inherited_alters.append(f'ALTER TABLE ONLY {qualified(name)} ALTER COLUMN {ident(col)} '
                                            f'SET DEFAULT {default};\n')
                if notnull:
                    inherited_alters.append(f'ALTER TABLE ONLY {qualified(name)} ALTER COLUMN {ident(col)} '
                                            'SET NOT NULL;\n')
                continue
            line = f'    {ident(col)} {typ}'
            if collation:
                line += f' COLLATE {ident(collation)}'
            if default is not None:
                line += f' DEFAULT {default}'
            if notnull:
                line += ' NOT NULL'
            lines.append(line)
        cr.execute("""
            SELECT p.relname FROM pg_catalog.pg_inherits i JOIN pg_catalog.pg_class p ON p.oid = i.inhparent
             WHERE i.inhrelid = %s ORDER BY i.inhseqno""", [oid])
        parents = [qualified(parent) for (parent,) in cr.fetchall()]
        inherits = f' INHERITS ({", ".join(parents)})' if parents else ''
        unlogged = 'UNLOGGED ' if persistence == 'u' else ''
        w(f'CREATE {unlogged}TABLE {qualified(name)} (\n' + ',\n'.join(lines) + f'\n){inherits};\n\n')
    for statement in inherited_alters:
        w(statement)
    w('\n')

    cr.execute("""
        SELECT s.relname, t.relname, a.attname FROM pg_catalog.pg_depend dep
          JOIN pg_catalog.pg_class s ON s.oid = dep.objid AND s.relkind = 'S'
          JOIN pg_catalog.pg_class t ON t.oid = dep.refobjid
          JOIN pg_catalog.pg_attribute a ON a.attrelid = t.oid AND a.attnum = dep.refobjsubid
         WHERE dep.classid = 'pg_class'::pg_catalog.regclass AND dep.refclassid = 'pg_class'::pg_catalog.regclass
           AND dep.deptype = 'a' AND s.relnamespace = %s ORDER BY s.relname""", [ns])
    for seq, table, column in cr.fetchall():
        w(f'ALTER SEQUENCE {qualified(seq)} OWNED BY {qualified(table)}.{ident(column)};\n')
    w('\n')

    for oid, name, _persistence in tables:
        cols = ', '.join(ident(c) for c in columns[oid])
        w(f'COPY {qualified(name)} ({cols}) FROM stdin;\n')
        out.flush()
        getattr(cr, '_obj', cr).copy_expert(f'COPY {qualified(name)} ({cols}) TO STDOUT', out)
        w('\\.\n\n')

    for _oid, name, *_rest in sequences:
        cr.execute(f'SELECT last_value, is_called FROM {qualified(name)}')
        value, called = cr.fetchone()
        w(f"SELECT pg_catalog.setval({literal(qualified(name))}, {value}, {'true' if called else 'false'});\n")
    w('\n')

    cr.execute(f"""
        SELECT c.relname, con.conname, pg_catalog.pg_get_constraintdef(con.oid), con.contype
          FROM pg_catalog.pg_constraint con JOIN pg_catalog.pg_class c ON c.oid = con.conrelid
         WHERE c.relnamespace = %s AND c.relkind = 'r' AND con.contype IN ('p', 'u', 'c', 'x', 'f')
           AND con.conislocal AND {_not_ext('pg_class', 'c.oid')}
         ORDER BY con.contype = 'f', c.relname, con.conname""", [ns])
    constraints = cr.fetchall()
    for table, name, definition, kind in constraints:
        if kind != 'f':
            w(f'ALTER TABLE ONLY {qualified(table)} ADD CONSTRAINT {ident(name)} {definition};\n')
    w('\n')

    cr.execute(f"""
        SELECT pg_catalog.pg_get_indexdef(i.indexrelid) FROM pg_catalog.pg_index i
          JOIN pg_catalog.pg_class t ON t.oid = i.indrelid
          JOIN pg_catalog.pg_class ic ON ic.oid = i.indexrelid
         WHERE t.relnamespace = %s AND t.relkind = 'r' AND {_not_ext('pg_class', 't.oid')}
           AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_constraint con
                            WHERE con.conindid = i.indexrelid AND con.conrelid = t.oid
                              AND con.contype IN ('p', 'u', 'x'))
         ORDER BY ic.relname""", [ns])
    for (definition,) in cr.fetchall():
        w(definition + ';\n')
    w('\n')

    for table, name, definition, kind in constraints:
        if kind == 'f':
            w(f'ALTER TABLE ONLY {qualified(table)} ADD CONSTRAINT {ident(name)} {definition};\n')
    w('\n')

    for name, definition in _views_in_dependency_order(cr, ns):
        w(f'CREATE VIEW {qualified(name)} AS\n{definition.rstrip().rstrip(";")};\n\n')

    cr.execute("""
        SELECT pg_catalog.pg_get_triggerdef(tg.oid) FROM pg_catalog.pg_trigger tg
          JOIN pg_catalog.pg_class c ON c.oid = tg.tgrelid
         WHERE c.relnamespace = %s AND NOT tg.tgisinternal ORDER BY c.relname, tg.tgname""", [ns])
    for (definition,) in cr.fetchall():
        w(definition + ';\n')
    w('\n')

    cr.execute(f"""
        SELECT c.relname, c.relkind, a.attname, d.description FROM pg_catalog.pg_description d
          JOIN pg_catalog.pg_class c ON c.oid = d.objoid AND d.classoid = 'pg_class'::pg_catalog.regclass
     LEFT JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid AND a.attnum = d.objsubid AND d.objsubid > 0
         WHERE c.relnamespace = %s AND c.relkind IN ('r', 'v', 'i', 'S') AND {_not_ext('pg_class', 'c.oid')}
         ORDER BY c.relname, d.objsubid""", [ns])
    kinds = {'r': 'TABLE', 'v': 'VIEW', 'i': 'INDEX', 'S': 'SEQUENCE'}
    for table, kind, column, text in cr.fetchall():
        if column:
            w(f'COMMENT ON COLUMN {qualified(table)}.{ident(column)} IS {literal(text)};\n')
        else:
            w(f'COMMENT ON {kinds[kind]} {qualified(table)} IS {literal(text)};\n')
    w('\n-- Dump complete\n')
