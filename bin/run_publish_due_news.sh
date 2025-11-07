#!/usr/bin/env bash
set -e
cd /var/www/html/hrms
/var/www/html/hrms/venv/bin/python manage.py publish_due_news
