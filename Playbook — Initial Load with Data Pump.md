# Playbook — Initial Load with Data Pump (expdp/impdp) + Oracle GoldenGate (CDC)

Purpose: ready-to-run steps to perform a bulk initial load using Data Pump (optionally offloaded to a physical standby) and then start GoldenGate for change-data-capture (CDC). Replace placeholders before running.

## Summary (recommended)
1. Record source SCN (SCN0).
2. Offload export: run expdp on standby or source (standby preferred for production).
3. Transfer dump files to target.
4. Import on target with impdp.
5. Configure GoldenGate (create users / dirs / param files).
6. Start GoldenGate extract from SCN0+1 (capture changes after export snapshot) and start replicat on target.
7. Validate and cut over.

## Variables — replace these before running
- SOURCE_TNS=SOURCE_TNS_ALIAS
- STANDBY_TNS=STANDBY_TNS_ALIAS
- TARGET_TNS=TARGET_TNS_ALIAS
- DP_DIR=DATA_PUMP_DIR            # Oracle DIRECTORY name on DB server
- DUMP_PREFIX=app_dump            # dump file name prefix
- PARALLEL=8
- SCHEMA_LIST=APP_SCHEMA
- GG_HOME=/u01/app/goldengate
- GG_USER=ggadmin
- GG_PWD=ChangeMe123!
- GG_SSH_USER=oracle              # OS user for file transfer (if needed)
- SSH_TARGET=target.example.com
- SSH_SOURCE=standby.example.com

---

## 0 — Prepare
- Ensure DP_DIR points to a filesystem with enough space on standby (or source) and target.
- Create directory objects on DBs if not present:
  SQL> CREATE DIRECTORY DATA_PUMP_DIR AS '/u01/dpdump';
  Grant read/write to the Data Pump user or schema used.

---

## 1 — Record source SCN (SCN0)
On source (or standby if you will export there, record SCN on *source primary* if you want strict resume point):
```sql
-- filepath: note-record-scn.sql
-- Connect as sysdba on SOURCE
SET PAGESIZE 0 FEEDBACK OFF VERIFY OFF HEADING OFF ECHO OFF
SELECT current_scn FROM v$database;
-- Save this value as SCN0 (e.g. 123456789)
```

Save SCN0 to a file: scn0.txt

---

## 2 — Export (run on standby if offloading)

Option A — run expdp on standby (recommended)
```bash
# filepath: scripts/expdp_on_standby.sh
# Run on standby host (linux). Replace placeholders.
export ORACLE_SID=STANDBY
expdp system/YourSysPwd@${STANDBY_TNS} \
  DIRECTORY=DATA_PUMP_DIR \
  DUMPFILE=${DUMP_PREFIX}_%U.dmp \
  LOGFILE=${DUMP_PREFIX}_exp.log \
  PARALLEL=${PARALLEL} \
  SCHEMAS=${SCHEMA_LIST} \
  FLASHBACK_SCN=${SCN0} \
  COMPRESSION=ALL
```
Notes:
- FLASHBACK_SCN with expdp ensures export consistent to that SCN (if supported).
- If you cannot use FLASHBACK_SCN, ensure export is consistent (use FLASHBACK_SCN or ensure read-consistent environment).

Option B — expdp on primary (if no standby available)
Same command but run against SOURCE_TNS.

---

## 3 — Transfer dump files to target
Use scp/rsync/WinSCP. Example (from your machine or standby):
```bash
# filepath: scripts/transfer_dumps.sh
scp /u01/dpdump/${DUMP_PREFIX}_*.dmp ${GG_SSH_USER}@${SSH_TARGET}:/u01/dpdump/
scp /u01/dpdump/${DUMP_PREFIX}_exp.log ${GG_SSH_USER}@${SSH_TARGET}:/u01/dpdump/
```

On Windows you can use WinSCP GUI or pscp.

---

## 4 — Import on Target with impdp
Run on target DB server:
```bash
# filepath: scripts/impdp_on_target.sh
export ORACLE_SID=TARGET
impdp system/YourSysPwd@${TARGET_TNS} \
  DIRECTORY=DATA_PUMP_DIR \
  DUMPFILE=${DUMP_PREFIX}_%U.dmp \
  LOGFILE=${DUMP_PREFIX}_imp.log \
  PARALLEL=${PARALLEL} \
  REMAP_TABLESPACE=users:users_new \
  TRANSFORM=SEGMENT_ATTRIBUTES:n
```

Alternative: impdp using NETWORK_LINK (pull directly from source; no dump files):
```bash
impdp system/YourSysPwd@${TARGET_TNS} \
  NETWORK_LINK=${SOURCE_TNS} \
  FULL=Y \
  PARALLEL=${PARALLEL} \
  LOGFILE=net_import.log
```
Notes:
- After import, run ANALYZE/DBMS_STATS as required.
- Keep the import consistent with the SCN0 snapshot recorded earlier.

---

## 5 — Prepare GoldenGate prerequisites

On source and target:
- Create GG directories (GG_HOME/dirprm, dirdat, dirrpt)
- Create GoldenGate database accounts and privileges on target
SQL on target:
```sql
-- filepath: sql/create_gg_user.sql
CREATE USER GGADMIN IDENTIFIED BY ${GG_PWD};
GRANT CONNECT, RESOURCE TO GGADMIN;
GRANT SELECT ANY TRANSACTION TO GGADMIN; -- adjust minimal privileges as per security policy
GRANT CREATE SESSION TO GGADMIN;
-- For many installs DBA privileges are used during setup; refine for production
```

Enable supplemental logging on source (required for GoldenGate capture):
```sql
ALTER DATABASE ADD SUPPLEMENTAL LOG DATA;
-- For each schema/table:
ALTER TABLE ${SCHEMA}.your_table ADD SUPPLEMENTAL LOG DATA (ALL) COLUMNS;
```

---

## 6 — GoldenGate parameter examples

6.1 — Data Pump / Extract on source (capture changes after SCN0)

Record SCN0 previously. Configure extract to STARTSCN greater than SCN0 so it captures changes after the export snapshot.

Example extract param:
```text
// filepath: d:\TODO\playbooks\gg\dirprm\extract_initial.prm
EXTRACT ext_src
USERID GGADMIN, PASSWORD ${GG_PWD}
EXTTRAIL ./dirdat/rt
DBOPTIONS STARTSCN ${SCN0}
TABLE ${SCHEMA}.*;
```
Note: `DBOPTIONS STARTSCN` or `STARTSCN` parameter is supported in Oracle GG variants; check your GG version syntax (alternatively use `STARTTIME` or `STARTSCN` in classic extract). If unsupported, start extract and let it capture live transactions—ensure you recorded SCN0 and coordinate with replicat to avoid duplicates.

6.2 — Replicat on target
```text
// filepath: d:\TODO\playbooks\gg\dirprm\replicat_initial.prm
REPLICAT rep_tgt
USERID GGADMIN, PASSWORD ${GG_PWD}
ASSUMETARGETDEFS
MAP ${SCHEMA}.*, TARGET ${SCHEMA}.%;
```

6.3 — Data Pump (GG data pump) — optional
```text
// filepath: d:\TODO\playbooks\gg\dirprm\datapump.prm
EXTRACT dpump
PASSTHRU
RMTHOST ${SSH_TARGET}, MPORT 7809
RMTTRAIL ./dirdat/rt
TABLE ${SCHEMA}.%;
```

---

## 7 — Start GoldenGate processes (GGSCI)

On source GG host:
```bash
cd ${GG_HOME}
./ggsci
GGSCI> CREATE SUBDIRS
GGSCI> START EXTRACT ext_src
GGSCI> INFO EXTRACT ext_src
```

On target GG host:
```bash
cd ${GG_HOME}
./ggsci
GGSCI> CREATE SUBDIRS
GGSCI> START REPLICAT rep_tgt
GGSCI> INFO REPLICAT rep_tgt
```

Verification:
- On source: GGSCI> STATS EXTRACT ext_src
- On target: GGSCI> STATS REPLICAT rep_tgt
- Check lag: GGSCI> INFO REPLICAT rep_tgt SHOWCH

---

## 8 — Validation & Cutover
1. Let GoldenGate replicate until lag = 0 (or acceptable low).
2. Quiesce application on source (stop writes).
3. Finalize: ensure all transactions up to cutover SCN are applied.
4. Stop extract on source, stop replicat if needed, point application to target.
5. Run verification queries (row counts, checksums) on critical tables.

Example quick row-count compare:
```sql
-- On source and target (use same query)
SELECT 'MYTABLE', COUNT(*) FROM ${SCHEMA}.MYTABLE;
```

---

## 9 — Cleanup & Notes
- Archive dump files after successful import.
- Remove temporary GG trails if not needed.
- Tighten GG user privileges for production.
- If your GoldenGate version supports integrated capture (no STARTSCN param), consult GG docs for exact param names (STARTSCN / STARTTIME).
- Test the whole flow in a staging environment before production.

---

## References / Helpful Commands
- impdp/expdp docs: use `parfile` for complex options.
- GoldenGate docs: validate exact EXTRACT/DBOPTIONS/STARTSCN syntax for your GG version.

---

End of playbook. Replace all uppercase placeholders and test in a non-production environment first.