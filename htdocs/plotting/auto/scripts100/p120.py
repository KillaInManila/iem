import psycopg2
from pyiem.network import Table as NetworkTable
from pandas.io.sql import read_sql
import datetime


def get_description():
    """ Return a dict describing how to call this plotter """
    d = dict()
    d['data'] = True
    d['description'] = """ """
    d['arguments'] = [
        dict(type='station', name='station', default='IA2203',
             label='Select Station'),
    ]
    return d


def plotter(fdict):
    """ Go """
    import matplotlib
    matplotlib.use('agg')
    pgconn = psycopg2.connect(database='coop', host='iemdb', user='nobody')
    cursor = pgconn.cursor()

    station = fdict.get('station', 'IA0200')

    table = "alldata_%s" % (station[:2], )
    nt = NetworkTable("%sCLIMATE" % (station[:2], ))
    cnt = {}
    for day in range(30, 183):
        cnt[day] = {32: 0.0, 28: 0.0, 26: 0.0, 22: 0.0}
    cnt_years = {32: 0.0, 28: 0.0, 26: 0.0, 22: 0.0}

    for base in (32, 28, 26, 22):
        # Query Last doy for each year in archive
        sql = """
            select year, max(extract(doy from day)) as doy from """+table+"""
            WHERE month < 7 and low <= %s and low > -40 and station = '%s'
            and month > 1
            GROUP by year ORDER by doy ASC
        """ % (base, station)
        cursor.execute(sql)
        cnt_years[base] = cursor.rowcount
        if cursor.rowcount == 0:
            return
        for row in cursor:
            cnt[row[1]][base] += 1.0

    sts = datetime.date(2000, 1, 1)
    running = {32: 0.0, 28: 0.0, 26: 0.0, 22: 0.0}
    res = """\
# IEM Climodat http://mesonet.agron.iastate.edu/climodat/
# Report Generated: %s
# Climate Record: %s -> %s
# Site Information: [%s] %s
# Contact Information: Daryl Herzmann akrherz@iastate.edu 515.294.5978
# Low Temperature exceedence probabilities
# (On a certain date, what is the chance a temperature below a certain
# threshold will be observed again that spring)
 DOY Date    <33  <29  <27  <23
""" % (datetime.date.today().strftime("%d %b %Y"),
       nt.sts[station]['archive_begin'].date(), datetime.date.today(), station,
       nt.sts[station]['name'])
    ar = []
    for day in range(181, 29, -1):
        ts = sts + datetime.timedelta(days=day-1)
        for base in (32, 28, 26, 22):
            running[base] += cnt[day][base]
        if day % 2 == 0:
            ar.append((" %3s %s  %3i  %3i  %3i  %3i"
                       "") % (ts.strftime("%-j"),
                              ts.strftime("%b %d"),
                              running[32] / cnt_years[32] * 100.0,
                              running[28] / cnt_years[28] * 100.0,
                              running[26] / cnt_years[26] * 100.0,
                              running[22] / cnt_years[22] * 100.0))

    ar.reverse()
    res += ("\n".join(ar))

    return None, None, res

if __name__ == '__main__':
    plotter(dict())
