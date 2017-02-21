"""Database found apache log entries of autoplot generation timing

Run from RUN_MIDNIGHT.sh
"""
import psycopg2
import datetime
import re

LOGRE = re.compile("Autoplot\[\s*(\d+)\] Timing:\s*(\d+\.\d+)s Key: ([^\s]*)")
LOGFN = '/var/log/mesonet/error_log'


def get_dbendts(cursor):
    cursor.execute("""SELECT max(valid) from autoplot_timing""")
    ts = cursor.fetchone()[0]
    if ts is None:
        ts = datetime.datetime.now() - datetime.timedelta(days=1)
    else:
        ts = ts.replace(tzinfo=None)
    return ts


def find_and_save(cursor, dbendts):
    now = datetime.datetime.now()
    thisyear = now.year
    for line in open(LOGFN):
        tokens = LOGRE.findall(line)
        if len(tokens) != 1:
            continue
        (appid, timing, uri) = tokens[0]
        valid = datetime.datetime.strptime("%s %s" % (thisyear, line[:15]),
                                           '%Y %b %d %H:%M:%S')
        if valid > now or valid <= dbendts:
            continue
        hostname = line.split()[3]
        cursor.execute("""
        INSERT into autoplot_timing (appid, valid, timing, uri, hostname)
        VALUES (%s, %s, %s, %s, %s)
        """, (appid, valid, timing, uri, hostname))


def main():
    mesosite = psycopg2.connect(database='mesosite', host='iemdb')
    cursor = mesosite.cursor()
    dbendts = get_dbendts(cursor)
    find_and_save(cursor, dbendts)
    cursor.close()
    mesosite.commit()

if __name__ == '__main__':
    main()
