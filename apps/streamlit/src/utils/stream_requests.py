import requests
import json
import pandas as pd
from datetime import date, timedelta
import os
import logging
from utils.shaping_df import shaping_metrics
import streamlit as st

logging.basicConfig(
    level=logging.INFO
)

## Basic payload model 
# payload={
#     "category": None,
#     "startDate": None,
#     "endDate": None,
#     "code": None,
#     "device": None,
#     "tag": None,
#     "max_records": 10,
#     "page_count": 1000
#     }

## Tag info :
# Iphone : "metrics"
# Workouts : "workouts"
# Spirometry : "spirometer"
# Manual data : "manual"
# State od minds : "stateofminds"

logger = logging.getLogger("Streamlit")

TOKEN = os.getenv("TOKEN", "")
PATIENT_ID = os.getenv("PATIENT_ID", "1797fcc2-2d95-47d6-9045-c188d9e1d02a")

def _date_today():
    return pd.Timestamp.now().date()

# Generic request
def _stream_request(
    patient_id: str, 
    token: str,
    payload: dict
    ):
    
    url = f"http://worker-stream/data/observation/{patient_id}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(url, headers=headers, json=payload).json()
    logger.info(f"URL : {url}")
    return response

# Tag stream request
def tag_stream_request(tag, lookback_days, max_records=5000, page_count=1000):
    logger.info("Start request :")
    end_date = _date_today()
    start_date = end_date - pd.Timedelta(days=lookback_days)
    logger.info(f"Starting date is : {start_date}")
    logger.info(f"Ending date is : {end_date}")
    
    payload={
            "startDate": str(start_date),
            "endDate": str(end_date),
            "tag": tag,
            "max_records": max_records,
            "page_count": page_count
        }
    logger.info(f"Payload is : {payload}")
    raw_data =  _stream_request(PATIENT_ID, TOKEN, payload)
    if raw_data:
        logger.info(f"Data count retrieved : {len(raw_data)}")
        return raw_data.get("data")
    else:
        logger.info("No data retrieved.")
        return None

if __name__ == "__main__":
    data = tag_stream_request("manual_weekly", 90)
    if data:
        df = shaping_metrics(data)
        print(df)
    else:
        print("No data retrieved")

    
    

