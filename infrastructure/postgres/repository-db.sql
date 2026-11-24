SELECT format('CREATE ROLE repository_user LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L', :'password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'repository_user')
\gexec

SELECT 'CREATE DATABASE repository_db OWNER repository_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'repository_db')
\gexec

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_database d JOIN pg_roles r ON r.oid = d.datdba
        WHERE d.datname = 'repository_db' AND r.rolname = 'repository_user'
          AND NOT (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls)
    ) THEN
        RAISE EXCEPTION 'Banco ou papel repository preexistente incompatível';
    END IF;
END $$;

REVOKE ALL ON DATABASE repository_db FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE repository_db TO repository_user;
