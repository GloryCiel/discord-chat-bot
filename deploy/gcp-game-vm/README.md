# Single-VM game selector

This setup keeps Palworld and Rust installed on one GCP VM while ensuring that
only the game selected in the VM's `active-game` metadata starts at boot.

## Preconditions

- `palworld.service` starts and gracefully stops Palworld.
- `rust.service` starts and gracefully stops Rust.
- Each service must save its world during `ExecStop` and finish within the GCP
  graceful shutdown window.
- Neither game service may be enabled directly at boot.

## Install the dispatcher

```bash
sudo install -m 0755 game-dispatcher.sh /usr/local/sbin/game-dispatcher
sudo install -m 0644 game-dispatcher.service /etc/systemd/system/game-dispatcher.service
sudo systemctl disable palworld.service rust.service
sudo systemctl daemon-reload
sudo systemctl enable game-dispatcher.service
```

Do not run `game-dispatcher.service` manually while players are connected. The
Discord bot writes the selected game to GCP metadata before it starts a stopped
VM. If the other game service is already active, the dispatcher refuses to
switch games.

## Required GCP permissions

Grant the bot's service account a custom role on the VM (or project) containing
these permissions:

- `compute.instances.get`
- `compute.instances.setMetadata`
- `compute.instances.start`
- `compute.instances.stop`
- `compute.zoneOperations.get`

Starting a VM also requires the bot to act as the service account attached to
that VM. On the attached service account itself, grant the bot
`roles/iam.serviceAccountUser` (`iam.serviceAccounts.actAs`). Grant this at the
service-account resource level instead of project-wide when possible.

Keep the service-account credential on the NAS that runs the Discord bot. Do
not copy it onto the public game VM.
