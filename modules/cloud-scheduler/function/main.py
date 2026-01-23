#!/usr/bin/env python3
"""
Sample scheduled job that demonstrates various operations:
- Data processing
- API calls
- Logging
- Error handling
"""

import os
import sys
import json
import logging
from datetime import datetime
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_data():
    """Simulate fetching data from an API"""
    try:
        logger.info("Fetching data from API...")
        response = requests.get(
            "https://api.github.com/repos/tensorflow/tensorflow",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        logger.info(f"Fetched repository: {data['name']}")
        return {
            "name": data["name"],
            "stars": data["stargazers_count"],
            "forks": data["forks_count"],
            "open_issues": data["open_issues_count"]
        }
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return None


def process_data(data):
    """Process the fetched data"""
    if not data:
        logger.warning("No data to process")
        return None
    
    logger.info("Processing data...")
    processed = {
        "timestamp": datetime.utcnow().isoformat(),
        "repository": data["name"],
        "metrics": {
            "stars": data["stars"],
            "forks": data["forks"],
            "issues": data["open_issues"],
            "popularity_score": data["stars"] + (data["forks"] * 2)
        }
    }
    logger.info(f"Processed data: {json.dumps(processed, indent=2)}")
    return processed


def send_notification(data):
    """Simulate sending a notification"""
    logger.info("Sending notification...")
    if data:
        logger.info(f"✓ Notification: Repository {data['repository']} has "
                   f"{data['metrics']['stars']} stars")
    else:
        logger.warning("No data to notify about")


def main():
    """Main function for the scheduled job"""
    logger.info("=" * 60)
    logger.info("Starting scheduled job execution")
    logger.info(f"Execution time: {datetime.utcnow().isoformat()}")
    logger.info(f"Environment: {os.getenv('ENV', 'production')}")
    logger.info("=" * 60)
    
    try:
        # Step 1: Fetch data
        data = fetch_data()
        
        # Step 2: Process data
        processed_data = process_data(data)
        
        # Step 3: Send notification
        send_notification(processed_data)
        
        # Step 4: Save results (simulated)
        if processed_data:
            logger.info("Job completed successfully!")
            logger.info(f"Results: {json.dumps(processed_data, indent=2)}")
            return 0
        else:
            logger.warning("Job completed with warnings")
            return 1
            
    except Exception as e:
        logger.error(f"Job failed with error: {e}", exc_info=True)
        return 1
    finally:
        logger.info("=" * 60)
        logger.info("Job execution finished")
        logger.info("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
