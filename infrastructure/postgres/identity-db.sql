SELECT format('CREATE ROLE %I LOGIN CREATEDB PASSWORD %L', :'identity_user', :'identity_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'identity_user')
\gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'identity_db', :'identity_user')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'identity_db')
\gexec

REVOKE ALL ON DATABASE :"identity_db" FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE :"identity_db" TO :"identity_user";
