"""METAR cloudiness"""
import datetime

import numpy as np
from pandas.io.sql import read_sql
from matplotlib import cm
from matplotlib.patches import Rectangle
from pyiem.network import Table as NetworkTable
from pyiem.plot.use_agg import plt
from pyiem.util import get_autoplot_context, get_dbconn, utc


def get_description():
    """ Return a dict describing how to call this plotter """
    desc = dict()
    desc['data'] = True
    desc['cache'] = 3600
    desc['description'] = """This chart is an attempted illustration of the amount
    of cloudiness that existed at a METAR site for a given month.  The chart
    combines reports of cloud amount and level to provide a visual
    representation of the cloudiness.  Once the METAR site hits a cloud level
    of overcast, it can no longer sense clouds above that level.  So while the
    chart will indicate cloudiness up to the top, it may not have been like
    that in reality.
    """
    today = datetime.date.today()
    desc['arguments'] = [
        dict(type='zstation', name='zstation', default='DSM',
             network='IA_ASOS', label='Select Station:'),
        dict(type='month', name='month', label='Select Month:',
             default=today.month),
        dict(type='year', name='year', label='Select Year:',
             default=today.year, min=1970),
    ]
    return desc


def plotter(fdict):
    """ Go """
    pgconn = get_dbconn('asos')
    ctx = get_autoplot_context(fdict, get_description())
    station = ctx['zstation']
    network = ctx['network']
    year = ctx['year']
    month = ctx['month']

    nt = NetworkTable(network)

    # Extract the range of forecasts for each day for approximately
    # the given month
    sts = utc(year, month, 1, 0, 0)
    ets = (sts + datetime.timedelta(days=35)).replace(day=1)
    days = (ets-sts).days
    data = np.ones((250, days * 24)) * -1
    vsby = np.ones((1, days * 24)) * -1

    df = read_sql("""
        SELECT valid, skyc1, skyc2, skyc3, skyc4, skyl1, skyl2, skyl3, skyl4,
        vsby from alldata where station = %s and valid BETWEEN %s and %s
        and report_type = 2
        ORDER by valid ASC
    """, pgconn, params=(station, sts, ets), index_col=None)

    lookup = {'CLR': 0, 'FEW': 25, 'SCT': 50, 'BKN': 75, 'OVC': 100}

    if df.empty:
        raise ValueError("No database entries found for station, sorry!")

    for _, row in df.iterrows():
        delta = int((row['valid'] - sts).total_seconds() / 3600 - 1)
        data[:, delta] = 0
        vsby[0, delta] = row['vsby']
        for i in range(1, 5):
            a = lookup.get(row['skyc%s' % (i,)], -1)
            if a >= 0:
                skyl = row['skyl%s' % (i,)]
                if skyl is not None and skyl > 0:
                    skyl = int(skyl / 100)
                    if skyl >= 250:
                        continue
                    data[skyl:skyl+4, delta] = a
                    data[skyl+3:, delta] = min(a, 75)

    data = np.ma.array(data, mask=np.where(data < 0, True, False))
    vsby = np.ma.array(vsby, mask=np.where(vsby < 0, True, False))

    fig = plt.figure(figsize=(8, 6))
    # vsby plot
    ax = plt.axes([0.1, 0.08, 0.8, 0.03])
    ax.set_xticks(np.arange(0, days*24+1, 24))
    ax.set_xticklabels(np.arange(1, days+1))
    ax.set_yticks([])
    cmap = cm.get_cmap('gray')
    cmap.set_bad('white')
    res = ax.imshow(
        vsby, aspect='auto', extent=[0, days*24, 0, 1], vmin=0, cmap=cmap,
        vmax=10)
    cax = plt.axes([0.915, 0.08, 0.035, 0.2])
    fig.colorbar(res, cax=cax)
    fig.text(0.02, 0.09, "Visibility\n[miles]", va='center')

    # clouds
    ax = plt.axes([0.1, 0.16, 0.8, 0.7])
    ax.set_facecolor('skyblue')
    ax.set_xticks(np.arange(0, days*24+1, 24))
    ax.set_xticklabels(np.arange(1, days+1))

    fig.text(
        0.5, 0.935,
        ('[%s] %s %s Clouds & Visibility\nbased on ASOS METAR Cloud Amount '
         '/Level and Visibility Reports'
         ) % (station, nt.sts[station]['name'], sts.strftime("%b %Y")),
        ha='center', fontsize=14)

    cmap = cm.get_cmap('gray_r')
    cmap.set_bad('white')
    cmap.set_under('skyblue')
    ax.imshow(np.flipud(data), aspect='auto', extent=[0, days*24, 0, 250],
              cmap=cmap, vmin=1)
    ax.set_yticks(range(0, 260, 50))
    ax.set_yticklabels(range(0, 25, 5))
    ax.set_ylabel("Cloud Levels [1000s feet]")
    fig.text(0.45, 0.02, "Day of %s (UTC Timezone)" % (sts.strftime("%b %Y"),))

    r1 = Rectangle((0, 0), 1, 1, fc='skyblue')
    r2 = Rectangle((0, 0), 1, 1, fc='white')
    r3 = Rectangle((0, 0), 1, 1, fc='k')
    r4 = Rectangle((0, 0), 1, 1, fc='#EEEEEE')

    ax.grid(True)

    ax.legend(
        [r1, r4, r2, r3], ['Clear', 'Some', 'Unknown', 'Obscured by Overcast'],
        loc='lower center', fontsize=14,
        bbox_to_anchor=(0.5, 0.99), fancybox=True, shadow=True, ncol=4)

    return fig, df


if __name__ == '__main__':
    plotter(dict(station='DSM', year=2016, month=9, network='IA_ASOS'))
