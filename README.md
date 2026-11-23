# splitview

Control LG webOS TV multi-view (split screen / PiP) programmatically over SSH, bypassing the on-screen menu.

Talks directly to the `com.webos.service.multiviewcontroller` Luna bus service on rooted LG webOS TVs.
Tested on an LG OLED with webOS 24.

## What it does

- Launch side-by-side or picture-in-picture with any two inputs (HDMI, LiveTV, apps)
- Switch between modes (sxs, pip, full)
- Move and resize the PiP window
- Switch audio between views
- Close multi-view

## Requirements

- LG webOS TV with root SSH access
- Python 3.9+, PySide6
- Passwordless SSH to TV (`ssh root@<tv-ip>`)

## API

All control goes through `luna-send` over SSH:

```sh
ssh -tt root@<tv-ip> 'luna-send -n 1 -f -a com.webos.app.multiviewsettings \
  "luna://com.webos.service.multiviewcontroller/launchApps" \
  "{\"apps\":[{\"appId\":\"com.webos.app.hdmi3\",\"order\":0},{\"appId\":\"com.webos.app.hdmi4\",\"order\":1}],\"mode\":\"sxs\",\"usageType\":\"normal\"}"'
```

### Modes

| Mode | Description |
|------|-------------|
| `sxs` | Side-by-side (also covers 3screen, 4screen, dual_monitor) |
| `pip` | Picture-in-picture (sub app in a corner) |
| `full` | Full screen (single app) |

### Key methods

| Method | Params | Effect |
|--------|--------|--------|
| `launchApps` | `{apps, mode, usageType}` | Launch or switch multi-view |
| `changeMode` | (none) | Cycle through modes |
| `changeSubAppPosition` | `{position}` | Move PiP window |
| `changeSubAppSize` | `{size}` | Resize PiP window |
| `closeMultiview` | `{}` | Exit multi-view |
| `getStatus` | `{}` | Current state |
| `switchAudio` | | Switch audio source |

## Status

API fully mapped and tested on a live TV. GUI controller is a prototype — works but needs a rebuild.
Not affiliated with LG.
