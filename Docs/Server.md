## Services
- APScheduler
- Auto SGP [Celery]
- Sportsbooks [Celery]
- Cron

### APScheduler
- Location: `/etc/systemd/system/ap-scheduler.service`
- Description: APScheduler service for Auto SGP
- Commands:
  - Start: `sudo systemctl start ap-scheduler`
  - Stop: `sudo systemctl stop ap-scheduler`
  - Restart: `sudo systemctl restart ap-scheduler`
  - Status: `sudo systemctl status ap-scheduler`
  - Logs: `sudo journalctl -u ap-scheduler -f`

## Auto SGP
- Worker Location: `/etc/systemd/system/auto-sgp-celery-worker.service`
- Beat Location: `/etc/systemd/system/auto-sgp-celery-beat.service`
- Description: Celery services for Auto SGP
- Commands:
  - Start Worker: `sudo systemctl start auto-sgp-celery-worker`
  - Stop Worker: `sudo systemctl stop auto-sgp-celery-worker`
  - Restart Worker: `sudo systemctl restart auto-sgp-celery-worker`
  - Status Worker: `sudo systemctl status auto-sgp-celery-worker`
  - Logs Worker: `sudo journalctl -u auto-sgp-celery-worker -f`
  - Start Beat: `sudo systemctl start auto-sgp-celery-beat`
  - Stop Beat: `sudo systemctl stop auto-sgp-celery-beat`
  - Restart Beat: `sudo systemctl restart auto-sgp-celery-beat`
  - Status Beat: `sudo systemctl status auto-sgp-celery-beat`
  - Logs Beat: `sudo journalctl -u auto-sgp-celery-beat -f`
  - Remove Beat: `rm /tmp/celerybeat-auto-sgp-schedule`

## Sportsbook Worker
- Worker Location: `/etc/systemd/system/sportsbook-celery-worker.service`
- Beat Location: `/etc/systemd/system/sportsbook-celery-beat.service`
- Description: Celery services for Sportsbook
- Commands
  - Start Worker: `sudo systemctl start sportsbook-celery-worker`
  - Stop Worker: `sudo systemctl stop sportsbook-celery-worker`
  - Restart Worker: `sudo systemctl restart sportsbook-celery-worker`
  - Status Worker: `sudo systemctl status sportsbook-celery-worker`
  - Logs Worker: `sudo journalctl -u sportsbook-celery-worker -f`
  - Start Beat: `sudo systemctl start sportsbook-celery-beat`
  - Stop Beat: `sudo systemctl stop sportsbook-celery-beat`
  - Restart Beat: `sudo systemctl restart sportsbook-celery-beat`
  - Status Beat: `sudo systemctl status sportsbook-celery-beat`
  - Logs Beat: `sudo journalctl -u sportsbook-celery-beat -f`
  - Remove Beat: `rm /tmp/celerybeat-sportsbook-schedule`

# Cron
- All Logs: `sudo tail -f /home/administrator/DifferentOdds-API-V2/logs/*.log`
- Example Single Log: `sudo tail -f /home/administrator/DifferentOdds-API-V2/logs/heartbeat.log`
- Confirm Running: `sudo grep CRON /var/log/syslog | tail -20`
