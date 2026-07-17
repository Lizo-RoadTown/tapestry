# Remote access — reach the platform from your laptop while travelling

Goal: when the platform stack is running on your desktop, your laptop (away from home, on hotel wi-fi, etc.) can hit the chat UI, Grafana, the API, all of it.

The platform doesn't care where you reach it from — only the host machine's network does. Two clean options:

## Option A: Tailscale (recommended)

Free, private (your devices only — not the public internet), no domain needed, no port forwarding, no public IP. Both machines join a "tailnet" and can reach each other by hostname.

### Setup (~5 min, one-time)

1. **Install Tailscale on the desktop** running the stack:
   - macOS / Windows: download from [tailscale.com/download](https://tailscale.com/download)
   - Linux: `curl -fsSL https://tailscale.com/install.sh | sh`
2. Sign in with Google / GitHub / Microsoft / email.
3. **Install Tailscale on your laptop**, sign in with the same account.
4. Both machines now appear in your tailnet at https://login.tailscale.com/admin/machines.

### Use it

On your laptop, visit:

| Service | URL |
|---------|-----|
| Chat UI (Next.js dev) | `http://<desktop-tailnet-name>:3000` (only when `npm run dev` is running locally) |
| Chat UI (production) | `https://humancensys.com` (lives on Vercel — reachable from anywhere already) |
| API | `http://<desktop-tailnet-name>:8001` |
| Grafana | `http://<desktop-tailnet-name>:3001` |
| API docs | `http://<desktop-tailnet-name>:8001/docs` |

`<desktop-tailnet-name>` is whatever Tailscale named your desktop (visible in the admin panel — typically `your-machine-name`). You can use the tailnet IP (`100.x.x.x`) instead if you prefer.

### Why this is the right default

- **Private** — the agent (which can do real things) isn't on the public internet
- **No DNS / domain / SSL** to manage
- **Zero compose changes** — Tailscale runs at the OS level; Docker port mappings just become reachable on the tailnet
- **Free** for personal use up to 100 devices

## Option B: Cloudflare Tunnel (when you DO want a public URL)

Use this if you want to share the agent (or Grafana dashboards) publicly, OR if you already have a domain on Cloudflare and want clean URLs like `chat.your-domain.com`.

1. Sign up for Cloudflare (free) and add your domain.
2. Cloudflare Zero Trust → Networks → Tunnels → create a tunnel.
3. Cloudflare gives you a token. Run `cloudflared tunnel run --token <TOKEN>` on your desktop (install cloudflared first).
4. In the tunnel's config, route `chat.your-domain.com` → `http://localhost:8000`, `grafana.your-domain.com` → `http://localhost:3001`, etc.
5. Cloudflare handles SSL automatically.

Trade-offs vs. Tailscale: public URLs (good for sharing, bad if you don't want exposure), more moving parts. Auth in front of public services becomes important — at minimum, set Grafana back to password-required mode (don't leave anonymous editor on a public URL).

Note: the chat UI itself is already public via Vercel at humancensys.com. The remote-access discussion here is about reaching the BACKEND services (API, Grafana, postgres) — the UI doesn't need a tunnel.

## Option C: Just put it in the cloud

If you don't want to depend on your desktop being on, deploy the stack to Render / Fly / Railway. Then your laptop just hits the public URL like any other website. See `platform/README.md` for that path. Costs money ongoing (~$7+/month). Not necessary for an "I want to reach this from my laptop" use case if Tailscale works for you.

## Recommendation

**Use Tailscale.** It's the right tool for "my desktop is at home, I want to reach it from elsewhere." Cloudflare Tunnel and cloud hosting are answering different questions (public sharing, always-on uptime).

If your desktop is asleep / off, you can't reach it via Tailscale either — that's a different problem (wake-on-LAN, or moving to cloud hosting). For occasional laptop access while the desktop is on, Tailscale is simplest.
