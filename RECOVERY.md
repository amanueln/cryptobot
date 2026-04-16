# CryptoBot Recovery Guide

## What Gets Backed Up

All database files are copied to your external drive:

| File | Contains |
|------|----------|
| `candles.db` | Price history, trade logs, equity snapshots, gate evaluations, scanner alerts |

**Backup location:** `/media/Media20TB/cryptobotBackup/`

- **Root files** — latest copy, overwritten each backup
- **`daily/` folder** — one snapshot per day, kept for 30 days

## How Backups Work

- **Automatic:** Every 6 hours while the container is running
- **Manual:** Hit the green **Backup** button on the momentum panel (next to Reset Data)

## Restoring After Uninstall / Reinstall

1. Install CryptoBot on ZimaOS from the app store
2. **Stop the container** before copying files
3. Copy the database from your backup drive to the app data folder:

```
cp /media/Media20TB/cryptobotBackup/candles.db /DATA/AppData/cryptobot/data/
```

4. Start the container — it picks up where it left off

## Restoring From a Daily Snapshot

If you need to go back to a specific day:

```
cp /media/Media20TB/cryptobotBackup/daily/candles_20260416.db /DATA/AppData/cryptobot/data/candles.db
```

Replace `20260416` with the date you want to restore.

## Volume Mounts (for reference)

These are the ZimaOS volume mappings that connect the container to persistent storage:

| ZimaOS Path | Container Path | Purpose |
|-------------|---------------|---------|
| `/DATA/AppData/cryptobot/data` | `/app/persistent` | Databases |
| `/DATA/AppData/cryptobot/config` | `/app/config` | Bot configuration |
| `/DATA/AppData/cryptobot/logs` | `/app/logs` | Log files |
| `/media/Media20TB/cryptobotBackup` | `/backup` | External drive backup |

## If Something Goes Wrong

- **Container won't start after restore:** Make sure the container is stopped before copying files. SQLite locks the database while in use.
- **Data looks old:** Check that you copied from the root backup (`candles.db`), not an older daily snapshot.
- **Backup button says "Failed":** The `/backup` volume mount may not be configured. Add it in ZimaOS container settings: `/media/Media20TB/cryptobotBackup` mapped to `/backup`.
