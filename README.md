# ☁️ Fanta-OFME-Cloud

Self-hosted save game synchronization server & web vault for **[Fanta OFME Downloader](https://github.com/ZuhuInc/Simple-OFME-Downloader-LIB)**.

Keep 100% control over your game saves on your own Unraid server, home lab, VPS, NAS, or Tailscale network — with automatic cross-PC sync, rolling backup history, multi-bucket API keys, and a built-in dark & gold Web Dashboard.

---

## ✨ Features

- **Plug-and-Play with Fanta OFME Downloader**: Native integration with the **Self-Hosted Cloud Server** provider in Fanta OFME Downloader.
- **Built-In Web Dashboard**: Inspect backed-up games, download `.zip` archives, upload saves manually, and manage API keys from your browser (`http://localhost:27845`).
- **Automatic Rolling History**: Before overwriting a cloud save, the server automatically preserves up to `5` historical versions per game so you can roll back to any previous session with one click.
- **API Keys & Bucket Isolation**:
  - Run in **Open LAN Mode** (zero config on trusted local networks / Tailscale) or generate **API Keys**.
  - Assign multiple PCs (e.g. Desktop + Laptop) to the same `default` bucket to share saves, or assign friends their own isolated bucket on the same server!
- **Rare Default Port (`27845`)**: Avoids port collisions with common Unraid / home server containers (`8080`, `8000`, `3000`, `5000`).

---

## 🚀 Quick Start

### Option 1: Unraid Server (Docker GUI)

1. In your Unraid WebUI, go to the **Docker** tab and click **Add Container** at the bottom.
2. Fill in the following fields:
   - **Name**: `Fanta-OFME-Cloud`
   - **Repository**: `ghcr.io/retr0777/fanta-ofme-cloud:latest`
   - **WebUI** *(enable Advanced View in top-right)*: `http://[IP]:[PORT:27845]`
3. Click **+ Add another Path, Port, Variable, Label or Device** to add the port and storage path:
   - **Port**:
     - Config Type: `Port`
     - Name: `WebUI & API Port`
     - Container Port: `27845`
     - Host Port: `27845`
     - Connection Type: `TCP`
   - **Path**:
     - Config Type: `Path`
     - Name: `Save Data Storage`
     - Container Path: `/app/data`
     - Host Path: `/mnt/user/appdata/fanta-ofme-cloud`
4. Click **Apply**! Once started, click the container icon and select **WebUI** (`http://<unraid-ip>:27845`).

### Option 2: Docker Compose

```bash
git clone https://github.com/ReTr0777/Fanta-OFME-Cloud.git
cd Fanta-OFME-Cloud
docker compose up -d
```

Open **`http://localhost:27845`** in your browser to access the Web Dashboard.

### Option 3: Direct Python (Windows / Linux)

```bash
git clone https://github.com/ReTr0777/Fanta-OFME-Cloud.git
cd Fanta-OFME-Cloud
pip install -r requirements.txt
python app.py
```
*(On Windows, you can also double-click `start.bat`)*

---

## 🔌 Connecting Fanta OFME Downloader

1. Open **Fanta OFME Downloader** and go to the **Cloud Saves** tab.
2. Select **Self-Hosted Cloud Server (`Fanta-OFME-Cloud`)**.
3. Enter your **Server URL** (e.g., `http://192.168.1.100:27845` or `https://cloud.yourdomain.com`).
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
