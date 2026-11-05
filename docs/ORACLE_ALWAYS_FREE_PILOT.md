# Oracle Cloud Always Free deployment (pilot)

This guide describes a zero-monthly-hosting-cost pilot, not a production availability guarantee. It is separate from the local-first setup.

## Decision and limits

Oracle Cloud Infrastructure (OCI) Always Free is the strongest free VM candidate for this Streamlit application because it provides an eligible Ampere A1 allocation equivalent to 2 OCPUs and 12 GB RAM, 200 GB combined block-volume storage, and 10 TB/month outbound transfer in the tenancy's home region. Exact eligibility and availability depend on OCI account limits and region capacity.

Official resource documentation:
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm

Critical limitations:
- OCI can reclaim idle Always Free compute instances. Its published idle test considers CPU, network, and (for A1) memory utilization over a seven-day period.
- Free compute is not an SLA-backed production service. A single VM is a single point of failure.
- Free capacity may be unavailable in the selected home region.
- Five volume backups are included in the Always Free allowance; this is not a substitute for independent, versioned database and document backups.
- This stack uses the application's existing SQLite persistence on a persistent VM volume. SQLite is not a horizontally scalable multi-instance database. Do not run multiple app replicas against this database.
- A free VM does not provide institutional incident response, managed patching, guaranteed recovery time, or contractual uptime.

Use only synthetic or otherwise approved low-risk pilot data until the institution has approved the data processing arrangement and recovery plan. Do not store patient-identifiable information, original confidential examination papers, or official learner records on this free pilot.

## Architecture

- OCI Ampere A1 VM (Ubuntu LTS, 2 OCPUs / up to 12 GB RAM within the free allocation).
- Docker Compose runs one USIPHU Streamlit process and Caddy.
- Caddy terminates HTTPS; port 8501 is not published to the internet.
- SQLite database, Source Inbox and local backup files live under the persistent runtime directory on the VM boot/block volume.
- Auth0 remains the OIDC identity provider.
- A second-provider object-storage destination (for example, Cloudflare R2 within its free allowance) should hold encrypted off-VM backups. R2's free allowance is limited to 10 GB-month storage, 1 million Class A operations and 10 million Class B operations; usage beyond that is chargeable.
  - https://developers.cloudflare.com/r2/pricing/

## 1. Create OCI resources

1. Create an OCI account at https://www.oracle.com/cloud/free/.
2. Choose the nearest home region with Always Free Ampere capacity. OCI's home region is selected during account setup and cannot simply be treated as a freely movable deployment region.
3. In the OCI console, create an Always Free-eligible Ubuntu VM.Standard.A1.Flex instance using no more than 2 OCPUs and 12 GB memory total.
4. Keep the boot volume within the 200 GB combined Always Free block-volume allocation.
5. Create a public subnet with an internet gateway and a reserved public IPv4 address if available in the account.
6. Configure the network security list / NSG to allow inbound TCP 22 only from the administrator's known IP, and TCP 80/443 from the internet. Do not open 8501, PostgreSQL, SSH to the world, or Docker's remote API.
7. Attach or use the persistent boot volume. Confirm the VM and storage resources are labelled Always Free eligible before creating them. Monitor OCI cost analysis and set a budget alert; an alert is not a hard spending cap.

If OCI reports out-of-capacity, do not create paid shapes or paid storage as a workaround.

## 2. Prepare the VM

Connect using SSH and install Docker Engine and the Docker Compose plugin from Docker's official Ubuntu instructions:
https://docs.docker.com/engine/install/ubuntu/

Create a restricted deployment user, enable unattended security updates, configure the host firewall, and keep SSH key-only. Do not use the root account for routine deployment.

Clone the repository and prepare persistent directories:

~~~bash
git clone https://github.com/usiphus/usiphu.git
cd usiphu
mkdir -p runtime/source_inbox runtime/backups .streamlit
chmod 700 runtime runtime/source_inbox runtime/backups .streamlit
sudo chown -R 10001:10001 runtime
~~~

The compose stack mounts runtime/ into the app container. Ensure the directory is on the persistent OCI volume and has ownership/permissions compatible with container UID 10001. Do not store runtime data inside the container image.

## 3. Configure domain and Auth0

Create a DNS A record for your domain pointing to the VM's reserved public IP. Set the domain in a root-owned .env file:

~~~dotenv
USIPHU_DOMAIN=usiphu.example.org
~~~

Create .streamlit/secrets.toml on the VM (never commit it):

~~~toml
USIPHU_ADMIN_SUBJECTS = "https://YOUR_AUTH0_DOMAIN/:AUTH0_ADMIN_SUBJECT"

[auth]
redirect_uri = "https://usiphu.example.org/oauth2callback"
cookie_secret = "REPLACE_WITH_A_LONG_RANDOM_SECRET"
client_id = "YOUR_AUTH0_CLIENT_ID"
client_secret = "YOUR_AUTH0_CLIENT_SECRET"
server_metadata_url = "https://YOUR_AUTH0_DOMAIN/.well-known/openid-configuration"
~~~

Use the exact issuer-qualified Auth0 subject format already used by USIPHU. Add the exact HTTPS callback URL and the app's HTTPS origin to the Auth0 Allowed Callback URLs and Allowed Logout URLs. Add stage reviewer subjects only after verifying each person's identity and role. Make the secrets file readable by the dedicated container UID only (for example, chown it to UID 10001 and set mode 600); keep the containing directory restricted to the deployment administrator.

## 4. Start and verify

Review the compose configuration, then:

~~~bash
docker compose -f docker-compose.oracle.yml config
docker compose -f docker-compose.oracle.yml up -d --build
docker compose -f docker-compose.oracle.yml ps
docker compose -f docker-compose.oracle.yml logs --tail=100 app proxy
~~~

Check:
- HTTPS certificate issuance and renewal.
- Auth0 login and logout.
- Admin, clinical reviewer and exam reviewer permissions with separate synthetic identities.
- Clinical approval before exam approval and two-person separation.
- Learner isolation and generated-draft isolation.
- Source upload, extraction, review and download.
- Restart persistence: restart containers and confirm records/files remain.
- Database integrity and a full restore into a clean test directory.

Do not merge or deploy this stack as a production release solely because the container health check passes.

## 5. Backups

The repository provides scripts/backup_sqlite.py and scripts/restore_backup.py. Run backups on a schedule while the app is quiesced or use a tested SQLite online-backup procedure. Copy the paired database backup, source archive and checksum to a separate provider/account. Encrypt backups before upload and restrict access to a dedicated backup credential.

The local backup directory on the same VM is only a short-term staging area; it is not an off-site backup. Test restoration at least monthly and after schema changes. Keep more than one dated backup generation. Monitor backup age and alert when a backup is missing or restore verification fails.

## 6. Production-readiness gate

This free single-VM arrangement is a pilot only. Before any real institutional production use, complete all of the following:

- Replace SQLite with a supported PostgreSQL deployment and test data migration.
- Move Source Inbox documents to durable object storage with private access, encryption and retention rules.
- Establish off-site encrypted backups, point-in-time recovery or equivalent, and a documented recovery point objective (RPO) / recovery time objective (RTO).
- Perform restore drills and verify database/document consistency.
- Add external uptime, resource, disk, TLS-expiry and backup monitoring.
- Apply host and container security updates, vulnerability scanning, least-privilege access, audit-log retention and incident response.
- Review Auth0 configuration, secrets rotation, privacy notice, consent, institutional data-processing approval and applicable Egyptian data-protection requirements.
- Load-test realistic concurrent learners and faculty reviewers.
- Decide how to recover if OCI reclaims the instance, the region loses capacity, or the account is suspended.
- Obtain a funded or institutionally supported fallback if uninterrupted service is required.

Do not describe this free pilot as production-ready. OCI's free compute is reclaimable and has no production uptime commitment. This guide provides a reproducible pilot deployment, not an SLA.


## 7. Automated encrypted off-VM backups

The repository includes `scripts/oracle_backup.sh`. It runs the existing SQLite online-backup and Source Inbox archive routine inside the app container, encrypts the database, Source Inbox archive and checksums with `age`, uploads only encrypted `.age` files to an independently configured rclone remote, and compares remote objects with `rclone check --download` before reporting success. It removes the just-created plaintext snapshot only after remote verification. Older local snapshots are pruned by the existing backup script. An optional Healthchecks-compatible ping URL sends success/failure heartbeats.

### Configure backup credentials

Install `age` and `rclone` on the VM. Generate an age keypair and keep the **private key offline**, not on the VM. Configure an rclone remote using a dedicated, least-privilege bucket credential. Keep bucket access private and configure provider-side lifecycle retention.

Create `/etc/usiphu/backup.env` as root, mode 0600:

~~~bash
sudo install -d -m 700 /etc/usiphu
sudo install -m 600 /dev/null /etc/usiphu/backup.env
sudoedit /etc/usiphu/backup.env
~~~

Contents (placeholders only):

~~~dotenv
AGE_RECIPIENT=age1yourpublicrecipient
RCLONE_REMOTE=r2:usiphu-backups
HEALTHCHECKS_PING_URL=https://hc-ping.com/YOUR-PRIVATE-UUID
~~~

The ping URL is a secret. Do not commit it or paste it into chat. Configure the rclone remote in a root-only config file (for example `/root/.config/rclone/rclone.conf`) and verify that root can access it.

Run a manual test:

~~~bash
sudo chmod 700 scripts/oracle_backup.sh
sudo scripts/oracle_backup.sh
~~~

Verify a dated folder containing encrypted files appears in the remote bucket. Perform a restore drill on a separate empty test directory: download the encrypted database, archive and checksum objects; decrypt them with the offline age private key; verify hashes; then use `scripts/restore_backup.py` to restore both database and Source Inbox. Never test a restore over the live runtime directory.

### Schedule daily backups

Create `/etc/cron.d/usiphu-backup`:

~~~cron
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
15 2 * * * root /opt/usiphu/scripts/oracle_backup.sh >> /var/log/usiphu-backup.log 2>&1
~~~

Adjust `/opt/usiphu` if the repository lives elsewhere. Create the log file with restricted permissions and configure log rotation. The script uses a lock to prevent overlapping runs. Alert on missed heartbeats in the external heartbeat service; cron without external alerting can fail silently.

**Cost boundary:** a second backup provider is only free while storage, operations and transfer remain within its free allowance. Set provider-side usage alerts and lifecycle expiry. A billing alert is not a hard spending cap. The VM's local backup folder alone is not an off-site backup.

## 8. Host firewall, patching and external monitoring

After confirming your SSH key works in a second terminal, apply the baseline firewall and host updates:

~~~bash
sudo USIPHU_SSH_CIDR="YOUR.ADMIN.PUBLIC.IP/32" bash scripts/oracle_host_hardening.sh
~~~

Do not use `0.0.0.0/0` for SSH. Configure the OCI Network Security Group/security list separately: TCP 22 only from the administrator CIDR; TCP 80/443 from the internet; no public 8501, database or Docker API ports. Docker can manipulate host firewall rules, so OCI network rules are the primary public boundary; verify from an external network that port 8501 is unreachable.

The Compose stack rotates container logs (10 MB × 5 files per service). Review host disk usage and logs regularly; log rotation is not centralized monitoring.

Configure an independent external HTTPS uptime monitor for `https://YOUR-DOMAIN/` and an alert contact. Configure the optional backup heartbeat above. Monitor HTTPS availability and certificate expiry, VM CPU/memory/disk, last successful off-site backup and restore-drill date, OCI usage/billing, failed SSH logins, unattended-upgrade status and Docker health.

The Streamlit container health check only verifies that the local process responds. It does not verify Auth0, database writes, source uploads, backup freshness or end-to-end user journeys.

## 9. Recovery runbook

If the app becomes unavailable:
1. Check OCI instance state, capacity/account notices and cost/Always Free eligibility.
2. SSH using the restricted administrator key; inspect Compose status, container logs and disk space.
3. If the container is unhealthy, inspect logs before restarting. Do not delete the runtime directory or recreate storage volumes.
4. If the VM or disk is lost, provision a replacement Always Free-eligible VM (if capacity exists), reinstall Docker, restore the repository and protected secrets, and point DNS only after the restore is verified.
5. Download the latest complete encrypted backup set, decrypt it offline, verify SHA-256 checksums, and restore into empty runtime paths using `scripts/restore_backup.py`.
6. Verify database integrity, Source Inbox files, Auth0 login, role separation and audit history using synthetic test accounts before reopening access.
7. Record the incident, recovery time and any data gap. If no verified off-site backup exists, preserve remaining disks/logs and do not overwrite them.

A monthly restore drill is mandatory for confidence in recovery. A single VM, free-tier reclaimability and free external services still provide no uptime or recovery SLA.
