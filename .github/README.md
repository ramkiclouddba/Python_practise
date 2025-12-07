# Oracle ZDM - Offline Migration with Golden Gate

A comprehensive guide for performing offline database migrations from Oracle databases using Zero Downtime Migration (ZDM) and Golden Gate replication technology.

## 📋 Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Architecture](#architecture)
- [Step-by-Step Configuration](#step-by-step-configuration)
- [ZDM Configuration](#zdm-configuration)
- [Golden Gate Setup](#golden-gate-setup)
- [Migration Execution](#migration-execution)
- [Validation & Cutover](#validation--cutover)
- [Troubleshooting](#troubleshooting)
- [References](#references)

## 🎯 Overview

This project provides a detailed, production-ready migration strategy for Oracle databases using:
- **Oracle ZDM** - Automated migration orchestration
- **Golden Gate** - Real-time data replication and capture
- **Offline Migration** - Minimal downtime approach

Ideal for migrating between Oracle versions, cloud environments, or hardware platforms.

## ✅ Prerequisites

### Software Requirements
- Oracle ZDM (v21.1 or later)
- Oracle Golden Gate (v19.1 or later)
- Source Oracle Database (11g or later)
- Target Oracle Database (same or higher version)
- Network connectivity between source and target systems

### System Requirements
- Minimum 4 CPU cores per server
- 16GB RAM minimum
- Sufficient disk space for trail files (1.5x source database size recommended)
- Linux/Unix or Windows operating systems supported

### User Permissions
- SYSDBA access on source and target databases
- OS-level permissions for Golden Gate directory

## 🏗️ Architecture

```
┌──────────────────┐          Trail Files           ┌──────────────────┐
│  Source Database │◄─────────────────────────────►│ Target Database  │
│                  │  Extract      Replicat          │                  │
│  (Production)    │  Process      Process           │  (New Instance)  │
└──────────────────┘                                 └──────────────────┘
         ▲                                                      ▲
         │                                                      │
         └──────────────────┬───────────────────────────────────┘
                            │
                   ┌────────▼─────────┐
                   │   ZDM Orchestrator│
                   │   (Monitoring)    │
                   └───────────────────┘
```

## 🚀 Step-by-Step Configuration

### Phase 1: Pre-Migration Assessment

1. **Verify Source Database**
   ```sql
   SELECT name, open_mode, log_mode FROM v$database;
   SELECT tablespace_name, status FROM dba_tablespaces;
   SELECT COUNT(*) FROM dba_tables;
   ```

2. **Check Golden Gate Compatibility**
   - Verify unsupported data types
   - Review LOB handling requirements
   - Plan supplemental logging strategy

3. **Prepare Target Environment**
   - Install target Oracle database
   - Set compatible parameter
   - Pre-create tablespaces if needed

## 🔧 ZDM Configuration

### Step 1: Create Response File

Create `zdm_migration_response.rsp`:

```properties
sourceDB.name=SOURCEDB
sourceDB.host=source.example.com
sourceDB.port=1521
sourceDB.user=sys
sourceDB.password=<encrypted>

targetDB.name=TARGETDB
targetDB.host=target.example.com
targetDB.port=1521
targetDB.user=sys
targetDB.password=<encrypted>

migration.type=OFFLINE
dataTransferMethod=GOLDENGATE
parallel.processes=4
```

### Step 2: Create Migration Job

```bash
zdmcli create-migration-job \
  -sourcedb SOURCEDB \
  -targetdb TARGETDB \
  -migrationtype OFFLINE \
  -datapumpparallel 4 \
  -rsp zdm_migration_response.rsp
```

## 🔄 Golden Gate Setup

### Source Database - Extract Configuration

#### Enable Supplemental Logging

```sql
ALTER DATABASE ADD SUPPLEMENTAL LOG DATA;
ALTER TABLE schema.table_name ADD SUPPLEMENTAL LOG DATA (ALL) COLUMNS;
```

#### Create Extract Process

**Parameter File: extract_config.prm**
```
EXTRACT extract_config
USERID ggadmin, PASSWORD ggadmin123
RMTHOST target.example.com, MPORT 7809
RMTTRAIL ./dirdat/rt
DDLOPTIONS ADDTRANSPORTKEY
TABLE scott.emp;
TABLE scott.dept;
```

**Commands:**
```bash
./ggsci
GGSCI> CREATE SUBDIRS
GGSCI> EDIT PARAMS EXTRACT_NAME
GGSCI> START EXTRACT extract_config
GGSCI> INFO EXTRACT extract_config
```

### Target Database - Replicat Configuration

#### Create Golden Gate User

```sql
CREATE USER ggadmin IDENTIFIED BY ggadmin123;
GRANT CONNECT, RESOURCE, DBA TO ggadmin;
```

#### Create Replicat Process

**Parameter File: replicat_config.prm**
```
REPLICAT replicat_config
USERID ggadmin, PASSWORD ggadmin123
ASSUMETARGETDEFS
DISCARDFILE ./dirrpt/replicat_config.dsc, PURGE
MAP scott.emp, TARGET scott.emp;
MAP scott.dept, TARGET scott.dept;
```

**Commands:**
```bash
./ggsci
GGSCI> CREATE SUBDIRS
GGSCI> EDIT PARAMS REPLICAT_NAME
GGSCI> START REPLICAT replicat_config
GGSCI> INFO REPLICAT replicat_config
```

## 📊 Migration Execution

### Start Migration

```bash
zdmcli start-migration-job -jobid ZDM_JOB_12345
```

### Monitor Progress

```bash
# Query job status
zdmcli query-migration-job -jobid ZDM_JOB_12345

# View detailed logs
zdmcli get-job-log -jobid ZDM_JOB_12345 -logtype main

# Monitor Golden Gate Extract
./ggsci
GGSCI> STATS EXTRACT extract_config

# Monitor Golden Gate Replicat
./ggsci
GGSCI> STATS REPLICAT replicat_config
```

## ✔️ Validation & Cutover

### Data Validation

```sql
-- Compare row counts
SELECT table_name, num_rows FROM user_tables ORDER BY table_name;

-- Validate indexes
SELECT index_name, status FROM user_indexes;

-- Check constraints
SELECT constraint_name, constraint_type FROM user_constraints;
```

### Cutover Steps

1. **Stop source application**
2. **Verify Golden Gate lag is zero**
3. **Stop Extract and Replicat processes**
4. **Perform final data validation**
5. **Switch application connection string to target**
6. **Verify application connectivity**

### Cleanup

```bash
# Remove trail files
rm -f /u01/app/goldengate_source/dirdat/*
rm -f /u01/app/goldengate_target/dirdat/*

# Archive migration logs
mkdir -p /backup/zdm_logs
cp /u01/zdm/logs/* /backup/zdm_logs/
```

## 🔍 Troubleshooting

| Issue | Cause | Resolution |
|-------|-------|-----------|
| Extract lag increasing | Network bottleneck | Increase parallel processes, check bandwidth |
| Replicat errors | Target space full | Extend tablespaces, check free space |
| Trail file full | Insufficient disk | Add secondary trails or increase trail size |
| ZDM job timeout | Long-running migration | Increase timeout, check network |
| Supplemental logging error | Invalid table name | Verify table exists and syntax is correct |

### Common Commands

```bash
# Check Golden Gate version
./ggsci --version

# View extract statistics
STATS EXTRACT extract_config, TOTALHOURS 24

# Troubleshoot replicat issues
VIEW REPORT REPLICAT replicat_config

# Enable debugging
EDIT PARAMS EXTRACT_NAME
# Add: DBOPTIONS DEBUGOPTIONS=16
```

## 📚 References

- [Oracle ZDM Documentation](https://docs.oracle.com/en/database/oracle/oracle-database/latest/zabod/oracle-zero-downtime-migration-introduction.html)
- [Golden Gate Administrator Guide](https://docs.oracle.com/en/middleware/goldengate/core/19.1/ggadm/)
- [Oracle Database Migration Best Practices](https://docs.oracle.com/en/database/oracle/oracle-database/latest/upgrd/index.html)

## 📝 License

This guide is provided as-is for educational and migration purposes.

## 👥 Support

For issues or questions:
1. Review troubleshooting section above
2. Check Oracle support documentation
3. Contact your database administration team

---

**Last Updated:** December 4, 2025  
**Version:** 1.0