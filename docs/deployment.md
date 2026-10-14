# Hackathon deployment on Oracle Cloud Always Free

This runs the existing Next.js frontend, FastAPI backend, and MySQL database on one Oracle Cloud VM. Only the HTTPS site is public. The API and database have no public ports. Start with a new, empty MySQL volume; do not copy the local `mysql-data` volume to the VM.

## Create the VM

1. Create an Oracle Cloud Free Tier account with Mumbai or Hyderabad as the **home region**. Choose an **Always Free** `VM.Standard.A1.Flex` Ubuntu instance with 2 OCPUs, 12 GB RAM, and a 50 GB boot volume. Confirm that every selected resource is marked Always Free before creating it.
2. Add an SSH public key and note the VM's public IP. Allow inbound TCP 80 and 443. Restrict TCP 22 to the administrator's IP address. Do not open 3000, 8000, or 3306.
3. Configure a domain or a free DuckDNS subdomain so its A record points to the VM's public IP. Wait until it resolves before starting Caddy.
4. Install Docker Engine with the Compose plugin on the VM using Docker's Ubuntu instructions. Allow the administrator to run Docker. Keep Ubuntu and Docker updated.

## Put the application on the VM

Transfer tracked repository files to the VM over SSH, excluding the local `.env`, virtual environments, build output, and Docker volumes. The private GitHub repository can also be cloned using a read-only deploy key. Do not put `.env` in Git or copy the local database volume.

On the VM, in the repository directory:

```bash
cp deploy/env.example .env
chmod 600 .env
```

Edit `.env` and set `APP_DOMAIN` to the DNS name, two different random MySQL passwords, and the SMTP sender credentials. Use a Gmail app password if using Gmail. The production Compose override sets `COOKIE_SECURE=true` and `APP_BASE_URL=https://<APP_DOMAIN>` automatically.

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
docker compose -f compose.yaml -f compose.prod.yaml ps
```

Caddy obtains and renews the HTTPS certificate automatically when the domain points to the VM and ports 80/443 are reachable. Visit `https://<APP_DOMAIN>` and check `https://<APP_DOMAIN>/api/health`. Create a new account and confirm that the verification email works before entering any patient information.

## Protect and maintain the database

MySQL data is stored in the `mysql-data` Docker volume on the VM's encrypted boot volume. Configure an Oracle boot-volume backup policy with retention that keeps no more than the five included Always Free backups. Make a manual backup before application upgrades, and test a restore to a separate VM before relying on backups. A volume snapshot is crash-consistent; for a database-consistent export, use `mysqldump` while MySQL is running and keep the export encrypted and access-restricted.

Do not run `docker compose down -v`: it deletes MySQL data. Restrict VM and Oracle account access, enable multi-factor authentication on the Oracle account, and rotate credentials if disclosed. The prediction models are research outputs without external clinical validation; do not use this deployment as a diagnostic service.

## Updates

After transferring an updated revision, run:

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
docker compose -f compose.yaml -f compose.prod.yaml ps
```

Check the app, email verification, and the health endpoint after each update.
