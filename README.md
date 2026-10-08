# SSH over standard WebSocket on Cloud Run

No separate VPS. OpenSSH listens only on 127.0.0.1:2222 inside the container.
The public endpoint is WSS (TLS) port 443, path `/`.
The bridge requires RFC 6455 WebSocket handshakes and binary frames, not raw
SSH following a fake HTTP 101 response. Client compatibility must be tested.
This is a password-login starter with the fixed username `tunneluser`.
SSH TCP forwarding is enabled for SSH tunneling; UDP is not natively provided.

## 1. GitHub

Create a repository named `ssh-websocket-cloudrun` at https://github.com/new.
Extract the ZIP on your computer. GitHub -> Add file -> Upload files.
Upload the CONTENTS of the folder (Dockerfile at the repository root), not the ZIP.
Include `.dockerignore` and `.gitignore` if uploading via git. No secrets belong
in the repository. This package does not configure automatic GitHub deployment.

## 2. Cloud Shell

Billing must be enabled. Use an account authorized to create services, build
images, manage secrets, and grant IAM access. Open https://shell.cloud.google.com.
Replace YOUR_GITHUB_USERNAME and YOUR_PROJECT_ID below.

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/ssh-websocket-cloudrun.git
cd ssh-websocket-cloudrun
export PROJECT_ID='YOUR_PROJECT_ID'
export REGION='europe-west1'
bash deploy.sh
```

Private repository: authenticate GitHub using `gh auth login` and use `gh repo
clone YOUR_GITHUB_USERNAME/ssh-websocket-cloudrun` instead of anonymous clone.
The script asks for the SSH password invisibly, stores it in Secret Manager,
creates a persistent SSH host key, and uses a dedicated runtime service account.
Save the printed fingerprint. Re-running reuses existing credentials.
Approve gcloud's Artifact Registry creation prompt if shown.
If a build fails for IAM reasons, read the error and grant the named build
service account the required build permissions; do not grant Owner broadly.
`--allow-unauthenticated` exposes the WebSocket endpoint; SSH still requires
the password. Organization policy might prohibit public ingress.

## 3. Client

Use an actual SSH-over-WebSocket/WSS mode, not VLESS and not plain SSH/TLS.

| Setting | Value |
|---|---|
| Address, Host, TLS SNI | Domain printed by deployment, without https:// |
| Port | 443 |
| TLS/WSS | Enabled; certificate verification enabled |
| WebSocket path | / |
| Username | tunneluser |
| Password | Password entered in deploy.sh |

Conceptual custom payload (replace YOUR_RUN_DOMAIN):

```text
GET / HTTP/1.1[crlf]Host: YOUR_RUN_DOMAIN[crlf]Upgrade: websocket[crlf]Connection: Upgrade[crlf][crlf]
```

This payload alone is incomplete. The client must add a random
`Sec-WebSocket-Key` and `Sec-WebSocket-Version: 13`, validate the upgrade, and
encode/decode binary WebSocket frames for SSH data. Do not merely paste a
static key into a raw SSH mode. Some HTTP Custom/Injector payload modes send
raw bytes after 101; those modes are incompatible with this implementation.
The new service URL differs from your existing VLESS service URL.

## 4. Check

```bash
RUN_URL=$(gcloud run services describe ssh-ws --region="$REGION" --format='value(status.url)')
curl "$RUN_URL/healthz"
gcloud run services logs read ssh-ws --region="$REGION" --limit=50
```

A local standard WebSocket banner test (no password transmitted):

```bash
python3 -m venv /tmp/ssh-ws-check
/tmp/ssh-ws-check/bin/pip install aiohttp==3.14.4
export RUN_URL
/tmp/ssh-ws-check/bin/python - <<'PY'
import asyncio, os, aiohttp
async def check():
    url = os.environ['RUN_URL'].replace('https://', 'wss://', 1) + '/'
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(url) as ws:
            msg = await ws.receive(timeout=15)
            assert msg.type == aiohttp.WSMsgType.BINARY, msg
            print(msg.data.decode(errors='replace'))
asyncio.run(check())
PY
```

Expected banner begins `SSH-2.0-OpenSSH_`. This checks transport, not password
authentication or Android application compatibility.

## 5. Update and stop

After committing new code to GitHub:

```bash
git pull --ff-only
bash deploy.sh
```

To stop and delete this service:

```bash
gcloud run services delete ssh-ws --region="$REGION"
```

This leaves build images and secrets; these are separate resources.

## Limits

Cloud Run WebSockets are requests with a maximum 60-minute request timeout.
Clients must reconnect. Instances can also restart sooner. Do not enable
HTTP/2 end-to-end. A WebSocket stays on one instance while connected, but new
connections can reach different instances. The shared host key prevents host
identity changes across those instances. Credentials are identical across
instances; filesystem edits and new users are not persistent.
The starting concurrency of 20 and maximum of 2 instances are test settings,
not a guarantee of capacity for 100 users. Active WebSockets, builds, outbound
data, and other Google Cloud resources can incur charges.

## Validation status

Bridge checked locally against a simulated SSH TCP endpoint, including binary
forwarding, normal HTTP rejection, and TCP disconnect cleanup. This environment
does not have Docker, so the image build, live SSH authentication, deployment,
and your Android client have not been tested here.

References:
- https://docs.cloud.google.com/run/docs/triggering/websockets
- https://docs.cloud.google.com/run/docs/configuring/services/secrets
- https://docs.cloud.google.com/sdk/gcloud/reference/run/deploy
