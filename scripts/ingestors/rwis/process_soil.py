""" Process Soil Data"""
import datetime

import pytz
import pandas as pd
from pandas.io.sql import read_sql
import requests
from pyiem.util import get_dbconn, logger, exponential_backoff


LOG = logger()
URI = (
    "https://services.arcgis.com/8lRhdTsQyJpO52F1/arcgis/rest/services/"
    "RWIS_Deep_Probe_Data_View/FeatureServer/0/query?where=1%3D1&f=pjson&"
    "outFields=*"
)


def clean2(val):
    """Clean again."""
    return None if pd.isnull(val) else val


def clean(val):
    """Clean our value."""
    try:
        val = float(val)
        if val > 200 or val < -50:
            val = None
    except ValueError:
        val = None
    return val


def process_features(features):
    """Process this feature."""
    rows = []
    for feat in features:
        props = feat["attributes"]
        valid = (
            datetime.datetime(1970, 1, 1)
            + datetime.timedelta(seconds=props["DATA_LAST_UPDATED"] / 1000.0)
        ).replace(tzinfo=pytz.UTC)
        rows.append(
            {
                "nwsli": props["NWS_ID"],
                "tmpf": clean(props["TEMPERATURE"]),
                "moisture": clean(props["MOISTURE"]),
                "valid": valid,
                "sensor_id": props["SENSOR_ID"],
            }
        )
    return pd.DataFrame(rows).set_index("nwsli")


def main():
    """Go Main Go."""
    res = exponential_backoff(requests.get, URI, timeout=30)
    if res is None:
        LOG.info("failed to fetch %s", URI)
        return
    data = res.json()
    df = process_features(data["features"])

    pgconn = get_dbconn("iem")
    xref = read_sql(
        "SELECT id, nwsli from rwis_locations", pgconn, index_col="nwsli"
    )
    df["location_id"] = xref["id"]

    cursor = pgconn.cursor()
    for nwsli, row in df.iterrows():
        if pd.isnull(nwsli) or pd.isnull(row["location_id"]):
            continue
        cursor.execute(
            "SELECT valid from rwis_soil_data where sensor_id = %s and "
            "location_id = %s",
            (row["sensor_id"], row["location_id"]),
        )
        if cursor.rowcount == 0:
            LOG.info("adding soil entry %s %s", nwsli, row["sensor_id"])
            cursor.execute(
                "INSERT into rwis_soil_data (valid, sensor_id, location_id) "
                "VALUES ('1980-01-01', %s, %s) RETURNING valid",
                (row["sensor_id"], row["location_id"]),
            )
        current = cursor.fetchone()[0]
        if row["valid"] <= current:
            continue
        cursor.execute(
            "UPDATE rwis_soil_data SET valid = %s, moisture = %s, temp = %s "
            "WHERE sensor_id = %s and location_id = %s",
            (
                row["valid"],
                clean2(row["moisture"]),
                clean2(row["tmpf"]),
                row["sensor_id"],
                row["location_id"],
            ),
        )
    cursor.close()
    pgconn.commit()
    pgconn.close()


if __name__ == "__main__":
    main()
