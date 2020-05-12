import datetime
from copy import deepcopy
from functools import partial
from typing import Sequence, Tuple, Optional, Union

import numpy as np
import plotly.graph_objects as go

from .utils import get_date_from_isoformat

PLOT_COLORS = [
    ('rgba(0,0,255,1)', 'rgba(0,0,255,0.25)'),
    ('rgba(255,0,0,1)', 'rgba(255,0,0,0.25)'),
    ('rgba(0,0,0,1)', 'rgba(0,0,0,0.25)'),
    ('rgba(128,0,240,1)', 'rgba(128,0,240,0.25)'),
    ('rgba(240,128,0,1)', 'rgba(240,128,0,0.25)'),
    ('rgba(0,128,240,1)', 'rgba(0,128,240,0.25)'),
    ('rgba(0,255,0,1)', 'rgba(0,255,0,0.25)'),
]


class Series:
    _x: np.ndarray
    x: np.ndarray
    y: np.ndarray

    def __init__(self, y: np.ndarray, x: Optional[Union[Sequence, np.ndarray]] = None,
                 start_date: Optional[Union[str, datetime.date]] = None):
        if (x is None) and (start_date is None):
            raise ValueError('Either x or start_date must be specified')
        if not start_date:
            assert list(x) == sorted(list(x))
            x = make_date_sequence(x)
            start_date = x[0]
            end_date = x[-1]
            num_elements = (end_date - start_date).days + 1
        else:
            if isinstance(start_date, str):
                start_date = get_date_from_isoformat(start_date)
            num_elements = len(y)
        self._x = np.array([start_date + datetime.timedelta(days=i) for i in range(num_elements)])
        if num_elements > len(y):
            last = 0.0
            x_to_y = map_x_to_y(x, y)
            new_y = []
            for day in self._x:
                last = x_to_y.get(day, last)
                new_y.append(last)
            y = new_y
        self.x = np.array([to_datetime(d) for d in self._x])
        if isinstance(y, np.ndarray):
            self.y = deepcopy(y)
        else:
            self.y = np.array(y)

    def __getitem__(self, item):
        item = self.get_index(item)
        return self.y[item]

    def __len__(self):
        return len(self.y)

    @property
    def start_date(self):
        return self._x[0]

    def get_index(self, x_value):
        if isinstance(x_value, str):
            x_value = get_date_from_isoformat(x_value)
        if isinstance(x_value, datetime.date):
            x_value = min(max((x_value - self.start_date).days, 0), len(self._x) - 1)
        return x_value

    def tolist(self):
        return self.y.tolist()

    def trim(self, start: Optional[Union[int, datetime.date, str]] = None,
             stop: Optional[Union[int, datetime.date, str]] = None):
        start_index = self.get_index(start or 0)
        stop_index = get_stop_index(self, stop)
        return Series(self.y[start_index:stop_index], self._x[start_index:stop_index])


def make_date_sequence(x: Sequence):
    x_date = []
    for day in x:
        if isinstance(day, datetime.datetime):
            day = day.isoformat()
        if isinstance(day, str):
            day = get_date_from_isoformat(day)
        x_date.append(day)
    return x_date


def map_x_to_y(x: Sequence, y: Sequence):
    assert len(x) == len(y)
    x_to_y = {}
    for xi, yi in zip(x, y):
        x_to_y[xi] = yi
    return x_to_y


def to_datetime(x: datetime.date) -> datetime.datetime:
    return datetime.datetime(*x.timetuple()[:3])


def get_stop_index(series, stop):
    stop_index = series.get_index(stop) + 1 if stop is not None else len(series)
    return min(stop_index, len(series))


def plot_line(fig, series, pop_name, color_index):
    fig.add_trace(go.Scatter(
        x=series.x,
        y=series.y,
        line_color=PLOT_COLORS[color_index][0],
        name=pop_name,
    ))


def concat_seq(s1, s2):
    if isinstance(s1, np.ndarray):
        return np.stack([s1, s2]).reshape(len(s1) + len(s2))
    return list(s1) + list(s2)


def plot_confidence_range(fig, series_low, series_high, legend, color_index):
    assert len(series_low.x) == len(series_high.x)
    fig.add_trace(go.Scatter(
        x=concat_seq(series_high.x, series_low.x[::-1]),
        y=concat_seq(series_high.y, series_low.y[::-1]),
        fill='toself',
        fillcolor=PLOT_COLORS[color_index][1],
        line_color=PLOT_COLORS[color_index][1],
        showlegend=legend is not None,
        name=legend,
    ))


def plot(
        pop_stats_name_tuples: Sequence[Tuple[Union['MetricResult', Series, Sequence[Series]], str]],
        title: str,
        log_scale: bool = False,
        size: Optional[int] = None,
        stop: Optional[int] = None,
        start: Optional[int] = None,
        ymax: Optional[float] = None,
        cindex: Optional[int] = None,
        show_confidence_interval: bool = True,
):
    fig = go.FigureWidget()
    area_fns = []
    line_fns = []

    for color_index, (data, pop_name) in enumerate(pop_stats_name_tuples):
        color_index = color_index % len(PLOT_COLORS)
        if cindex is not None:
            color_index = cindex
        if isinstance(data, Series) or len(data) == 1:
            line_fn = partial(plot_line, fig, data[0].trim(start, stop), pop_name, color_index)
            line_fns.append(line_fn)
        elif len(data) == 3:
            if show_confidence_interval:
                area_fn = partial(plot_confidence_range, fig, data[1].trim(start, stop), data[2].trim(start, stop),
                                  None, color_index)
                area_fns.append(area_fn)
            line_fn = partial(plot_line, fig, data[0].trim(start, stop), pop_name, color_index)
            line_fns.append(line_fn)
        elif len(data) == 2:
            area_fn = partial(plot_confidence_range, fig, data[0].trim(start, stop), data[1].trim(start, stop),
                              pop_name, color_index)
            area_fns.append(area_fn)
        else:
            raise ValueError('Invalid number of elements to plot')

    for area_fn in area_fns:
        area_fn()

    for line_fn in line_fns:
        line_fn()

    fig.update_layout(
        title=title)
    if ymax:
        fig.update_yaxes(range=[1 if log_scale else 0, ymax])
    if log_scale:
        fig.update_layout(yaxis_type="log")
    if size:
        fig.update_layout(width=size)
    if len(pop_stats_name_tuples) == 1:
        fig.update_layout(showlegend=False)
    return fig
