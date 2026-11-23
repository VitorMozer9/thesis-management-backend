SELECT format('CREATE ROLE defense_user LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L', :'password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'defense_user')
\gexec

SELECT 'CREATE DATABASE defense_db OWNER defense_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'defense_db')
\gexec

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_database d JOIN pg_roles r ON r.oid = d.datdba
        WHERE d.datname = 'defense_db' AND r.rolname = 'defense_user'
          AND NOT (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls)
    ) THEN
        RAISE EXCEPTION 'Banco ou papel defense preexistente incompatível';
    END IF;
END $$;

REVOKE ALL ON DATABASE defense_db FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE defense_db TO defense_user;
