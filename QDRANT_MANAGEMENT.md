# Qdrant Management Guide

Quick reference for managing and backing up your self-hosted Qdrant vector database.

---

## 🚀 Quick Health Check

**Production:**
```bash
make prod_qdrant-stats
```

**Expected output:**
```
Collection: artworks_prod_v1 (Production)
Points: **Number of poins*
Status: green
Vectors: text_clip, image_clip, text_jina, image_jina
```

**Development:**
```bash
make qdrant-stats
```

---

## 📊 Inspection Commands

### Collection Info
```bash
make prod_qdrant-info      # Detailed JSON info (point count, vectors, indices)
make prod_qdrant-health    # Health check endpoint
make prod_qdrant-logs      # View last 50 log lines
```

### Quick Checks
```bash
# List all collections
make prod_qdrant-collections

# View Qdrant container logs
docker compose -f docker-compose.prod.yml logs qdrant --tail=100
```

---

## 🖥️ Accessing Qdrant Web UI

The Web UI lets you browse data, test queries, and debug issues.

### On Production Server

**Step 1: From your LOCAL machine, create SSH tunnel:**
```bash
ssh -L 6333:localhost:6333 kristian@your-server-address
```

**Step 2: Open in browser:**
```
http://localhost:6333/dashboard
```

Keep the SSH connection open while using the UI.

**Shortcut to see instructions:**
```bash
make prod_qdrant-ui-tunnel
```

---

## 💾 Backup Strategy

### Option 1: Qdrant Snapshots (Recommended)

Snapshots are Qdrant's built-in backup mechanism. They create a point-in-time backup of your collection.

#### How Snapshots Work

**Where are snapshots stored?**
- Snapshots are stored **inside the Docker volume** on your server: `/qdrant/storage/collections/artworks_prod_v1/snapshots/`
- They persist as long as the Docker volume exists
- They survive container restarts

**Do I need to download them?**
- **For disaster recovery: YES** - Download snapshots to your local machine for off-site backup
- **For quick local restore: NO** - Snapshots on the server can be used directly
- **Best practice:** Keep the latest 2-3 snapshots on the server, download monthly snapshots for long-term backup

**What happens to old snapshots?**
- Snapshots **do NOT expire automatically** - you must delete them manually
- They take up disk space (~same size as your collection data)
- Recommended: Keep only recent snapshots on server, delete old ones after downloading

---

#### Creating a Snapshot

```bash
make prod_qdrant-snapshot
```

This creates a snapshot with timestamp: `artworks_prod_v1-YYYY-MM-DD-HH-MM-SS.snapshot`

**Storage location on server:**
```
/var/lib/docker/volumes/live-app_qdrant_data/_data/collections/artworks_prod_v1/snapshots/
```

---

#### Listing Snapshots

```bash
docker compose -f docker-compose.prod.yml exec web curl -s \
  http://qdrant:6333/collections/artworks_prod_v1/snapshots
```

**Example output:**
```json
{
  "result": {
    "snapshots": [
      {
        "name": "artworks_prod_v1-2026-01-11-14-30-00.snapshot",
        "creation_time": "2026-01-11T14:30:00Z",
        "size": 1073741824
      }
    ]
  }
}
```

---

#### Downloading Snapshot (Off-site Backup)

**Step 1: List snapshots to find the name**
```bash
docker compose -f docker-compose.prod.yml exec web curl -s \
  http://qdrant:6333/collections/artworks_prod_v1/snapshots
```

**Step 2: Download to your local machine**
```bash
# Replace SNAPSHOT_NAME with actual name from step 1
docker compose -f docker-compose.prod.yml exec web curl -s \
  http://qdrant:6333/collections/artworks_prod_v1/snapshots/SNAPSHOT_NAME \
  > qdrant-backup-$(date +%Y%m%d).snapshot
```

**File size:** ~1-2 GB for full collection (268,096 points)

**Recommended frequency:** Monthly downloads, keep last 3 months locally

---

#### Restoring from Snapshot

**Scenario 1: Restore from snapshot still on server**
```bash
# List snapshots
docker compose -f docker-compose.prod.yml exec web curl -s \
  http://qdrant:6333/collections/artworks_prod_v1/snapshots

# Restore (Qdrant will use the snapshot file already on server)
docker compose -f docker-compose.prod.yml exec web curl -X PUT \
  "http://qdrant:6333/collections/artworks_prod_v1/snapshots/SNAPSHOT_NAME/recover"
```

**Scenario 2: Restore from downloaded snapshot**
```bash
# 1. Upload snapshot file back to server
scp qdrant-backup-20260111.snapshot kristian@your-server:/tmp/

# 2. On server, restore via upload
cd /path/to/project
docker compose -f docker-compose.prod.yml exec -T web curl -X POST \
  "http://qdrant:6333/collections/artworks_prod_v1/snapshots/upload" \
  --data-binary @/tmp/qdrant-backup-20260111.snapshot
```

---

#### Deleting Old Snapshots

```bash
# Delete a specific snapshot (replace SNAPSHOT_NAME)
docker compose -f docker-compose.prod.yml exec web curl -X DELETE \
  http://qdrant:6333/collections/artworks_prod_v1/snapshots/SNAPSHOT_NAME
```

**When to delete:**
- After downloading for off-site backup
- When you have too many old snapshots consuming disk space
- Keep at least 1-2 recent snapshots on server for quick recovery

### Option 2: Docker Volume Backup

**Backup the entire Qdrant data volume:**
```bash
# On production server
docker run --rm \
  -v live-app_qdrant_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/qdrant-backup-$(date +%Y%m%d).tar.gz /data
```

**Restore from volume backup:**
```bash
# 1. Stop Qdrant
docker compose -f docker-compose.prod.yml stop qdrant

# 2. Restore volume
docker run --rm \
  -v live-app_qdrant_data:/data \
  -v $(pwd):/backup \
  alpine sh -c "cd / && tar xzf /backup/qdrant-backup-YYYYMMDD.tar.gz"

# 3. Start Qdrant
docker compose -f docker-compose.prod.yml start qdrant
```

### Option 3: Re-index from S3 (Disaster Recovery)

If both Qdrant backups are lost, you can rebuild from your S3 image storage and PostgreSQL database.

**Process:**
1. Images are stored in S3 bucket: `semantic-art-thumbnails-prod-v1`
2. Metadata is in PostgreSQL: `TransformedData` table
3. Run the ETL load-embeddings command to regenerate collection:

```bash
# This will recreate the collection from scratch using S3 images
make prod_load-embeddings
```

**Time estimate:** ~3-4 hours to re-index all 268,096 artworks.

---

## 🔧 Maintenance Tasks

### Check Disk Space
```bash
# On production server
docker volume inspect live-app_qdrant_data | grep Mountpoint
# Then: df -h /path/from/mountpoint
```

### Monitor Collection Health
```bash
# Should always be "green"
make prod_qdrant-info | grep status
```

**Status meanings:**
- **green**: Healthy, all operations normal
- **yellow**: Rebuilding indices, searches may be slower
- **red**: Problem detected, check logs

### View Search Query Logs
```bash
make prod_qdrant-logs
```

Look for entries like:
```
POST /collections/artworks_prod_v1/points/query HTTP/1.1" 200
```

---

## 🆘 Troubleshooting

### App shows "Connection refused"
```bash
# Check if Qdrant is running
docker compose -f docker-compose.prod.yml ps qdrant

# Restart if needed
docker compose -f docker-compose.prod.yml restart qdrant
```

### Slow search performance
```bash
# Check collection status (should be "green")
make prod_qdrant-info | grep status

# Check if indices exist
make prod_qdrant-info | grep -A 10 payload_schema
```

**Expected indices:** `museum`, `searchable_work_types`, `object_number`

### Out of disk space
1. Check disk usage (see "Check Disk Space" above)
2. Consider creating and downloading snapshot, then deleting old snapshots
3. Scale up server disk if needed

### Data corruption
1. Stop Qdrant: `docker compose -f docker-compose.prod.yml stop qdrant`
2. Restore from latest snapshot (see "Restore from snapshot" above)
3. If no snapshot available, re-index from S3 (see "Option 3" above)

---

## 📅 Recommended Maintenance Schedule

### Weekly
- ✅ Run `make prod_qdrant-stats` to verify point count
- ✅ Check logs for errors: `make prod_qdrant-logs`

### Monthly
- ✅ Create and download snapshot: `make prod_qdrant-snapshot`
- ✅ Verify disk space usage
- ✅ Test a few search queries via Web UI

### Quarterly
- ✅ Test backup restoration process on dev environment
- ✅ Review and clean up old snapshots

---

## 🔐 Security Notes

- Qdrant is **NOT exposed** to the internet (internal Docker network only)
- Web UI only accessible via SSH tunnel or from server localhost
- No authentication required for internal access
- Data persists in Docker volume: `live-app_qdrant_data`

---

## 📚 Key Files

- **docker-compose.prod.yml**: Qdrant service configuration
- **.env.prod**: Qdrant connection settings
- **Makefile**: Management commands (run `make help`)
- **PRODUCTION_QDRANT_MIGRATION.md**: Migration documentation (historical reference)

---

## 📞 Quick Reference

```bash
# Health check
make prod_qdrant-stats

# Access Web UI
make prod_qdrant-ui-tunnel

# Create backup
make prod_qdrant-snapshot

# View logs
make prod_qdrant-logs

# Emergency re-index (if backups lost)
make prod_load-embeddings
```
