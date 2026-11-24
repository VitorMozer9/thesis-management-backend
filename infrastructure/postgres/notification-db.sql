SELECT format('CREATE ROLE notification_user LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L', :'password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'notification_user')
\gexec

SELECT 'CREATE DATABASE notification_db OWNER notification_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'notification_db')
\gexec

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_database d JOIN pg_roles r ON r.oid = d.datdba
        WHERE d.datname = 'notification_db' AND r.rolname = 'notification_user'
          AND NOT (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls)
    ) THEN
        RAISE EXCEPTION 'Banco ou papel notification preexistente incompatível';
    END IF;
END $$;

REVOKE ALL ON DATABASE notification_db FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE notification_db TO notification_user;
