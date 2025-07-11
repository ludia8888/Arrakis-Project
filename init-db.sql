-- Initialize databases for Arrakis MSA

-- Create databases
CREATE DATABASE IF NOT EXISTS user_service_db;
CREATE DATABASE IF NOT EXISTS audit_db;
CREATE DATABASE IF NOT EXISTS oms_db;

-- Grant permissions (adjust as needed)
GRANT ALL PRIVILEGES ON DATABASE user_service_db TO arrakis_user;
GRANT ALL PRIVILEGES ON DATABASE audit_db TO arrakis_user;
GRANT ALL PRIVILEGES ON DATABASE oms_db TO arrakis_user;