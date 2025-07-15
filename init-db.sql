-- Create databases (PostgreSQL compatible)
\c postgres;
SELECT 'CREATE DATABASE user_service_db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'user_service_db')\gexec
SELECT 'CREATE DATABASE audit_db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'audit_db')\gexec
SELECT 'CREATE DATABASE oms_db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'oms_db')\gexec
SELECT 'CREATE DATABASE scheduler_db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'scheduler_db')\gexec

-- Create oms_user role if not exists
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'oms_user') THEN

      CREATE ROLE oms_user LOGIN PASSWORD 'oms_password';
   END IF;
END
$do$;
