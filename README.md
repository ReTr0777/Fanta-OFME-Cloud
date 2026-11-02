# ☁️ Fanta-OFME-Cloud

Self-hosted save game synchronization server & web vault for **[Fanta OFME Downloader](https://github.com/ZuhuInc/Simple-OFME-Downloader-LIB)**.

Keep 100% control over your game saves on your own Unraid server, Ubuntu VPS, home lab, Synology NAS, or Tailscale network — with automatic cross-PC sync, rolling backup history, multi-bucket API keys, and a built-in dark & gold Web Dashboard.

---

## ✨ Features

- **Plug-and-Play with Fanta OFME Downloader**: Native integration with the **Self-Hosted Cloud Server** provider in Fanta OFME Downloader.
- **Built-In Web Dashboard**: Inspect backed-up games, download `.zip` archives, upload saves manually, and manage API keys from your browser (`http://localhost:27845`).
- **Automatic Rolling History**: Before overwriting a cloud save, the server automatically preserves up to `5` historical versions per game so you can roll back to any previous session with one click.
- **API Keys & Bucket Isolation**:
  - Run in **Open LAN Mode** (zero config on trusted local networks / Tailscale) or generate **API Keys**.
  - Assign multiple PCs (e.g. Desktop + Laptop / ROG Ally / Steam Deck) to the same `default` bucket to share saves, or assign friends their own isolated bucket on the same server!
- **Rare Default Port (`27845`)**: Avoids port collisions with common home server containers (`8080`, `8000`, `3000`, `5000`).

---

## 🚀 Deployment Guides (Choose Your Server)

Click on your server platform below for step-by-step installation instructions:

<details open>
<summary><strong>🟠 Unraid Server (Docker GUI or Compose Manager)</strong></summary>
<br>

### Method A: Native Unraid Docker GUI
1. In your Unraid WebUI, go to the **Docker** tab and click **Add Container** at the bottom.
2. Toggle **Advanced View** (top-right corner) and fill in:
   - **Name**: `Fanta-OFME-Cloud`
   - **Repository**: `ghcr.io/retr0777/fanta-ofme-cloud:latest`
   - **WebUI**: `http://[IP]:[PORT:27845]`
3. Click **+ Add another Path, Port, Variable, Label or Device** to add the port and storage path:
   - **Port**:
     - **Config Type**: `Port`
     - **Name**: `WebUI & API Port`
     - **Container Port**: `27845`
     - **Host Port**: `27845`
     - **Connection Type**: `TCP`
   - **Path**:
     - **Config Type**: `Path`
     - **Name**: `Save Data Storage`
     - **Container Path**: `/app/data`
     - **Host Path**: `/mnt/user/appdata/fanta-ofme-cloud`
4. Click **Apply**! Once started, click the container icon and select **WebUI** (`http://<unraid-ip>:27845`).

### Method B: Unraid Compose Manager Plugin
Paste the following into a new stack in **Docker &rarr; Compose**:
```yaml
services:
  fanta-ofme-cloud:
    image: ghcr.io/retr0777/fanta-ofme-cloud:latest
    container_name: Fanta-OFME-Cloud
    restart: unless-stopped
    ports:
      - "27845:27845"
    volumes:
      - /mnt/user/appdata/fanta-ofme-cloud:/app/data
```
</details>

<details>
<summary><strong>🐧 Ubuntu / Debian Linux Server (Docker Compose)</strong></summary>
<br>

1. **Install Docker & Docker Compose** (if not already installed):
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
   sudo systemctl enable --now docker
   ```
2. **Clone & Start the Server**:
   ```bash
   git clone https://github.com/ReTr0777/Fanta-OFME-Cloud.git
   cd Fanta-OFME-Cloud
   sudo docker compose up -d
   ```
3. **Allow Port `27845` Through UFW Firewall** (if UFW is enabled):
   ```bash
   sudo ufw allow 27845/tcp
   ```
4. Open **`http://<your-ubuntu-server-ip>:27845`** in your browser!
</details>

<details>
<summary><strong>🐧 Ubuntu / Debian Linux Server (Bare-Metal Python + systemd Service)</strong></summary>
<br>

If you prefer running directly on Ubuntu/Debian without Docker:

1. **Install Python 3 & Clone the Repo**:
   ```bash
   sudo apt update && sudo apt install -y python3 python3-venv python3-pip git
   sudo git clone https://github.com/ReTr0777/Fanta-OFME-Cloud.git /opt/fanta-ofme-cloud
   cd /opt/fanta-ofme-cloud
   sudo python3 -m venv .venv
   sudo .venv/bin/pip install -r requirements.txt
   ```
2. **Create a `systemd` Service** so it runs 24/7 and starts on boot:
   ```bash
   sudo tee /etc/systemd/system/fanta-ofme-cloud.service > /dev/null <<EOF
   [Unit]
   Description=Fanta-OFME-Cloud Save Sync Server
   After=network.target

   [Service]
   Type=simple
   WorkingDirectory=/opt/fanta-ofme-cloud
   Environment="FANTA_DATA_DIR=/opt/fanta-ofme-cloud/data"
   Environment="FANTA_PORT=27845"
   ExecStart=/opt/fanta-ofme-cloud/.venv/bin/gunicorn --bind 0.0.0.0:27845 --workers 2 --threads 4 --timeout 120 app:app
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   EOF
   ```
3. **Enable & Start the Service**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now fanta-ofme-cloud
   sudo systemctl status fanta-ofme-cloud
   ```
</details>

<details>
<summary><strong>📦 Synology NAS / CasaOS / Portainer / TrueNAS</strong></summary>
<br>

In **Portainer Stacks**, **Synology Container Manager (Project)**, or **CasaOS Custom Install**, deploy using this Compose configuration:

```yaml
services:
  fanta-ofme-cloud:
    image: ghcr.io/retr0777/fanta-ofme-cloud:latest
    container_name: fanta-ofme-cloud
    restart: unless-stopped
    ports:
      - "27845:27845"
    environment:
      - FANTA_SERVER_NAME=Fanta-OFME-Cloud
      - FANTA_MAX_HISTORY=5
    volumes:
      - ./data:/app/data
```
*(On Synology NAS, replace `./data` with `/volume1/docker/fanta-ofme-cloud/data`)*.
</details>

<details>
<summary><strong>🪟 Windows PC / Windows Server</strong></summary>
<br>

1. Install [Python 3.10+](https://www.python.org/downloads/) (check *"Add Python to PATH"* during installation).
2. Clone or download this repository:
   ```powershell
   git clone https://github.com/ReTr0777/Fanta-OFME-Cloud.git
   cd Fanta-OFME-Cloud
   pip install -r requirements.txt
   ```
3. Double-click **`start.bat`** (or run `python app.py`).
4. Open **`http://localhost:27845`** in your browser.
</details>

---

## 🌐 Remote Access (Connecting From Outside Your Home Network)

<details>
<summary><strong>🔒 Option 1: SWAG Reverse Proxy (Unraid / LinuxServer.io)</strong></summary>
<br>

A ready-to-use SWAG proxy configuration is included at [`swag/fanta-ofme-cloud.subdomain.conf`](swag/fanta-ofme-cloud.subdomain.conf).

1. Ensure your `Fanta-OFME-Cloud` container is on the same custom Docker network as `swag` (e.g. `proxynet`), or set `$upstream_app` to your server's LAN IP.
2. Copy [`swag/fanta-ofme-cloud.subdomain.conf`](swag/fanta-ofme-cloud.subdomain.conf) into `/mnt/user/appdata/swag/nginx/proxy-confs/fanta-ofme-cloud.subdomain.conf`.
3. Add `saves` to your DNS CNAME records and SWAG `SUBDOMAINS` list, then restart **SWAG**.
4. Connect in **Fanta OFME Downloader** using `https://saves.yourdomain.com` + your **API Key**!
</details>

<details>
<summary><strong>🟢 Option 2: Nginx Proxy Manager (NPM)</strong></summary>
<br>

1. In Nginx Proxy Manager, click **Hosts &rarr; Proxy Hosts &rarr; Add Proxy Host**.
2. **Details Tab**:
   - **Domain Names**: `saves.yourdomain.com`
   - **Scheme**: `http`
   - **Forward Hostname / IP**: `<your-server-ip>` (or `fanta-ofme-cloud`)
   - **Forward Port**: `27845`
   - Enable **Block Common Exploits**.
3. **SSL Tab**: Request a new Let's Encrypt SSL certificate and enable **Force SSL**.
4. **Advanced Tab**: Add the following line so large save `.zip` archives can upload:
   ```nginx
   client_max_body_size 512M;
   ```
5. Click **Save**!
</details>

<details>
<summary><strong>☁️ Option 3: Cloudflare Tunnel (Zero Port Forwarding)</strong></summary>
<br>

1. In your **Cloudflare Zero Trust Dashboard**, go to **Networks &rarr; Tunnels** and select your tunnel.
2. Add a **Public Hostname**:
   - **Subdomain**: `saves`
   - **Domain**: `yourdomain.com`
   - **Service Type**: `HTTP`
   - **URL**: `<your-server-lan-ip>:27845`
3. Save the hostname and connect in **Fanta OFME Downloader** using `https://saves.yourdomain.com` + your **API Key**.
</details>

<details>
<summary><strong>🦊 Option 4: Tailscale / Tailscale Funnel (No Domain Required)</strong></summary>
<br>

- **Private Mesh (For Your Own Devices)**: Install Tailscale on your server and your gaming PCs/handhelds, then use `http://<tailscale-ip>:27845`.
- **Public HTTPS Link for Friends (Tailscale Funnel)**:
  ```bash
  tailscale funnel --bg 27845
  ```
  Tailscale will give you a permanent `https://<machine-name>.<tailnet>.ts.net` URL you can paste directly into **Fanta OFME Downloader**.
</details>

---

## 🔌 Connecting Fanta OFME Downloader

1. Open **Fanta OFME Downloader** and go to the **Cloud Saves** tab.
2. Select **Self-Hosted Cloud Server (`Fanta-OFME-Cloud`)**.
3. Enter your **Server URL** (e.g., `http://192.168.1.100:27845` or `https://saves.yourdomain.com`).
4. *(Optional)* Paste an **API Key** generated in the Web Dashboard under **API Keys & Connect**.
5. Click **Test Connection** to verify latency and click **Save Preferences**!

---

## ⚙️ Environment Variables (`.env`)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `FANTA_PORT` | `27845` | Port the server listens on |
| `FANTA_SERVER_NAME` | `Fanta-OFME-Cloud` | Display name shown in the Web Dashboard and client connection test |
| `FANTA_API_KEY` | *(empty)* | Optional master API key pre-registered in the `default` bucket |
| `FANTA_ADMIN_PASSWORD` | *(empty)* | Optional password to lock the Web Dashboard |
| `FANTA_REQUIRE_AUTH` | `false` | Require an API key even when no keys are defined yet |
| `FANTA_MAX_HISTORY` | `5` | Number of rolling historical backup `.zip` files kept per game |
| `FANTA_MAX_UPLOAD_MB` | `512` | Maximum upload size per save archive in MB |

---

## 📡 REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/status` | Server health, version, and auth verification |
| `GET` | `/api/saves` | List all backed-up saves in the caller's bucket |
| `GET` | `/api/saves/<safe_name>` | Inspect metadata and rolling history for a single game |
| `POST` | `/api/saves/<safe_name>` | Upload `<safe_name>_save.zip` (`multipart/form-data` with `file`, `title`, `mtime`) |
| `GET` | `/api/saves/<safe_name>/download` | Download active save `.zip` (or `?version=<filename>` for history) |
| `DELETE` | `/api/saves/<safe_name>` | Delete cloud save and history for a game |
