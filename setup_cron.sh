#!/bin/bash
# ============================================================================
# setup_cron.sh — Sets up the daily ETL cron job
#
# Usage:
#   chmod +x setup_cron.sh
#   ./setup_cron.sh
#
# This adds a cron job that runs the ETL pipeline daily at 06:00 UTC.
# GA4 data from 2 days ago is pulled (the default behaviour of etl_pipeline.py).
# ============================================================================

# Configuration — adjust these paths to match your server
ETL_DIR="/opt/analytics-dashboard"
PYTHON="/opt/analytics-dashboard/venv/bin/python"
LOG_FILE="/var/log/analytics-etl.log"

echo "================================================"
echo "  Analytics ETL — Cron Job Setup"
echo "================================================"
echo ""

# Check if the ETL script exists
if [ ! -f "$ETL_DIR/etl_pipeline.py" ]; then
    echo "ERROR: etl_pipeline.py not found at $ETL_DIR"
    echo "Please copy the project files to $ETL_DIR first."
    exit 1
fi

# Check if the .env file exists
if [ ! -f "$ETL_DIR/.env" ]; then
    echo "WARNING: .env file not found at $ETL_DIR"
    echo "Copy .env.example to .env and fill in your credentials before running."
fi

# Create log file if it doesn't exist
sudo touch "$LOG_FILE"
sudo chown $(whoami):$(whoami) "$LOG_FILE"

# Define the cron job
CRON_JOB="0 6 * * * cd $ETL_DIR && $PYTHON etl_pipeline.py >> $LOG_FILE 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "etl_pipeline.py"; then
    echo "Cron job already exists. Current crontab:"
    crontab -l | grep "etl_pipeline"
    echo ""
    read -p "Replace it? (y/n): " REPLACE
    if [ "$REPLACE" != "y" ]; then
        echo "Keeping existing cron job."
        exit 0
    fi
    # Remove old entry
    crontab -l | grep -v "etl_pipeline.py" | crontab -
fi

# Add the cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo ""
echo "Cron job installed:"
echo "  $CRON_JOB"
echo ""
echo "The ETL pipeline will run daily at 06:00 UTC."
echo "Logs will be written to: $LOG_FILE"
echo ""
echo "To verify, run: crontab -l"
echo "To test manually: cd $ETL_DIR && $PYTHON etl_pipeline.py --dry-run"
echo ""
echo "Done!"
