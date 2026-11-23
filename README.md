# splitview

Unlock multi-view (split screen / PiP) on LG webOS TVs without an LG account or a "supported" TV model.

LG gates multi-view behind a mandatory login that harvests your data, and even after signing in, many models will reject perfectly valid HDMI combos with fake "incompatible input" errors. The hardware is fully capable — LG just locks it. This tool bypasses all of that by talking directly to the internal Luna bus service that the TV's own UI uses, skipping every software restriction.

Requires root SSH access via [RootMyTV](https://rootmy.tv) or equivalent. Tested on an LG OLED (webOS 24).

## What it does

- Launch side-by-side or picture-in-picture with any two inputs (HDMI, LiveTV, apps)
- Switch between modes (sxs, pip, full)
- Move and resize the PiP window
- Switch audio between views
- Close multi-view
- No LG account required, no "incompatible input" gatekeeping

## Requirements

- LG webOS TV with root SSH access ([RootMyTV](https://rootmy.tv))
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

## Why this exists

LG's multi-view feature is built into the TV's firmware on models that officially "don't support" it. The `com.webos.service.multiviewcontroller` service is present and fully functional — LG just doesn't expose it through the normal UI unless you sign in and have a model they've decided to allow. This tool calls the same internal API the TV's own settings app uses, with no account check and no input validation gatekeeping.

## Status

API fully mapped and tested on a live TV. GUI controller is a prototype.
Not affiliated with LG.
