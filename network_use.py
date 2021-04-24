#! /usr/bin/env python3

# network_use - Display wifi transfer rate in a graph
# Copyright (C) 2016, Amir Livne Bar-on
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
import cairo
import time
import os

def poll_wifi_byte_counts():
    """
    Returns (total RX bytes, total TX bytes) for a random wlan iface
    """
    with open('/proc/net/dev') as netdev:
        for line in netdev:
            if line.startswith('wl'):
                words = line.split()
                return int(words[1]), int(words[9])

class TimeIndexedData(object):
    def __init__(self, required_time_span):
        """
        Save events, ordered by time. Keep at least for `required_time_span`
        """
        self._events = []
        self._time_span = required_time_span

    def __bool__(self):
        return bool(self._events)

    def _since(self, start):
        return [(t, ev) for (t, ev) in self._events if t >= start]

    def _total_time_span(self):
        if self:
            return 0.0
        return self._events[-1][0] - self._events[0][0]

    def first_event_time(self):
        if self:
            return self._events[0][0]

    def last_event_time(self):
        if self:
            return self._events[-1][0]

    def add(self, info):
        self._events.append((time.time(), info))
        if self._total_time_span() > self._time_span * 2:
            self._events = self._since(self.last_event_time() - self._time_span)

    def segment(self, start_time, end_time):
        """
        Includes the events surrounding the timespan. That is, one before
        and one after the open segment (start_time, end_time), if exists.
        """
        assert not self or start_time <= end_time
        start_ind = 0
        while (start_ind < len(self._events)-1) and \
              (self._events[start_ind+1][0] <= start_time):
            start_ind += 1
        end_ind = start_ind
        while (end_ind < len(self._events)-1) and \
              (self._events[end_ind][0] < end_time):
            end_ind += 1
        return self._events[start_ind:end_ind+1]

    def right_segment(self, duration):
        """
        Events from the last `duration` seconds
        """
        if not self:
            return []
        return self._since(self.last_event_time() - duration)

POLLING_TIME_MILLISECONDS = 250
ICON_FILE_NAME = 'network_use.png'
MARGIN_TOP = 32
MARGIN_BOTTOM = 16
MARGIN_X = 40
TICK_LENGTH = 6
SCALE_X = 12
CLEAR_SIZE = 16
GRADIENT_SIZE = 32
RECOMPUTE_SCALE_EXTRA_TIME = 0.5 # seconds
GRAPH_STYLE = {
    'recv': {'color': (1.0, 0.0, 0.0), 'width': 2.0},
    'send': {'color': (0.0, 0.7, 1.0), 'width': 1.5}
}

class GraphView(Gtk.DrawingArea):
    def __init__(self, data):
        Gtk.DrawingArea.__init__(self)
        self._data = data
        self._graph_start_time = None
        self.connect('draw', self.on_draw)

    def on_draw(self, w, cr):

        self._size = self.get_allocation()

        self._recompute_graph_start_time()
        time_for_axis_scaling = (self._size.width - MARGIN_X * 2.0 - CLEAR_SIZE) / SCALE_X + RECOMPUTE_SCALE_EXTRA_TIME
        data_for_axis_scaling = self._data.right_segment(time_for_axis_scaling)
        usable_plot_height = self._size.height - MARGIN_TOP - MARGIN_BOTTOM
        axis_scaling = {'recv': GraphView._axis_scale(data_for_axis_scaling, 'recv', usable_plot_height),
                        'send': GraphView._axis_scale(data_for_axis_scaling, 'send', usable_plot_height)}

        self._clear_background(cr)
        self._draw_axes(cr, axis_scaling)

        # restrict plot area
        cr.rectangle(MARGIN_X + 1, MARGIN_TOP, self._size.width - MARGIN_X * 2.0 - 1, self._size.height - MARGIN_TOP - MARGIN_BOTTOM)
        cr.clip()

        self._plot_previous_screen(cr, axis_scaling)
        self._plot_current_screen(cr, axis_scaling)

    def _recompute_graph_start_time(self):
        if self._graph_start_time is None and self._data:
            # data didn't previously exist and does now
            self._graph_start_time = self._data.first_event_time()

        if self._data.first_event_time() != self._data.last_event_time():
            # non-trivial data
            swipe_duration = (self._size.width - MARGIN_X * 2.0) / SCALE_X
            while self._data.last_event_time() - self._graph_start_time > swipe_duration:
                # longer than window size
                self._graph_start_time += swipe_duration

    @staticmethod
    def _axis_scale(data, key, plot_height):
        max_value = max([1.0] + [info[key] for (t, info) in data])
        for (base, name) in [(1, 'B'), (2**10, 'KB'), (2**20, 'MB')]:
            for factor in [1, 2, 5, 10, 20, 50, 100, 200, 500]:
                if base == 1 and factor < 50:
                    continue
                if base * factor * 4.0 > max_value:
                    return {'unit': name, 'tick': factor, 'scale': base*factor*4.0}

    def _clear_background(self, cr):
        cr.rectangle(0, 0, self._size.width, self._size.height)
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.fill()

    def _draw_axes(self, cr, axis_scaling):

        width, height = self._size.width, self._size.height

        # graph frame
        cr.move_to(MARGIN_X + 0.5, MARGIN_TOP + 0.5)
        cr.line_to(MARGIN_X + 0.5, height - MARGIN_BOTTOM + 0.5)
        cr.line_to(width - MARGIN_X + 0.5, height - MARGIN_BOTTOM + 0.5)
        cr.line_to(width - MARGIN_X + 0.5, MARGIN_TOP + 0.5)
        cr.set_source_rgb(0.0, 0.0, 0.0)
        cr.set_line_width(1.0)
        cr.stroke()

        cr.select_font_face('Verdana')
        # left label
        label = 'recv {}/s'.format(axis_scaling['recv']['unit'])
        extent = cr.text_extents(label)
        cr.move_to(TICK_LENGTH, MARGIN_TOP - extent[3] / 2.0 - TICK_LENGTH * 1.5)
        cr.set_source_rgb(*GRAPH_STYLE['recv']['color'])
        cr.show_text(label)
        # right label
        label = 'send {}/s'.format(axis_scaling['send']['unit'])
        extent = cr.text_extents(label)
        cr.move_to(width - extent[2] - TICK_LENGTH, MARGIN_TOP - extent[3] / 2.0 - TICK_LENGTH * 1.5)
        cr.set_source_rgb(*GRAPH_STYLE['send']['color'])
        cr.show_text(label)

        # tick marks
        cr.set_source_rgb(0.0, 0.0, 0.0)
        cr.set_line_width(1.0)
        for i in range(5):
            y = round(height - MARGIN_BOTTOM - (height - MARGIN_TOP - MARGIN_BOTTOM)*i/4.0) + 0.5
            # left
            cr.move_to(MARGIN_X + 0.5, y)
            cr.line_to(MARGIN_X + 0.5 - TICK_LENGTH, y)
            cr.stroke()
            label = '{}'.format(i * axis_scaling['recv']['tick'])
            extent = cr.text_extents(label)
            cr.move_to(MARGIN_X + 0.5 - TICK_LENGTH * 1.5 - extent[0] - extent[2] - 1, y - extent[1] - extent[3] * 0.5 - 1)
            cr.show_text(label)
            # right
            cr.move_to(width - MARGIN_X + 0.5, y)
            cr.line_to(width - MARGIN_X + 0.5 + TICK_LENGTH, y)
            cr.stroke()
            label = '{}'.format(i * axis_scaling['send']['tick'])
            extent = cr.text_extents(label)
            cr.move_to(width - MARGIN_X + 0.5 + TICK_LENGTH * 1.5 + extent[0], y - extent[1] - extent[3] * 0.5 - 1)
            cr.show_text(label)

    def _plot_previous_screen(self, cr, axis_scaling):

        if self._graph_start_time is None:
            # the no-data scenario messes up the calculations
            return

        width, height = self._size.width, self._size.height

        swipe_duration = (width - MARGIN_X * 2.0) / SCALE_X
        data = self._data.segment(self._data.last_event_time() - swipe_duration, self._graph_start_time)
        prev_start_time = self._graph_start_time - swipe_duration
        self._plot_trend_line(cr, data, prev_start_time, axis_scaling, 'send')
        self._plot_trend_line(cr, data, prev_start_time, axis_scaling, 'recv')

        # fade in
        last_x = (self._data.last_event_time() - self._graph_start_time) * SCALE_X
        cr.rectangle(MARGIN_X, 0, last_x + CLEAR_SIZE, height)
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.fill()
        gradient = cairo.LinearGradient(MARGIN_X + last_x + CLEAR_SIZE, 0, MARGIN_X + last_x + CLEAR_SIZE + GRADIENT_SIZE, 0)
        gradient.add_color_stop_rgba(0, 1, 1, 1, 1)
        gradient.add_color_stop_rgba(1, 1, 1, 1, 0)
        cr.rectangle(MARGIN_X + last_x + CLEAR_SIZE, 0, GRADIENT_SIZE, height)
        cr.set_source(gradient)
        cr.fill()

    def _plot_current_screen(self, cr, axis_scaling):
        data = self._data.segment(self._graph_start_time, self._data.last_event_time())
        self._plot_trend_line(cr, data, self._graph_start_time, axis_scaling, 'send')
        self._plot_trend_line(cr, data, self._graph_start_time, axis_scaling, 'recv')

    def _plot_trend_line(self, cr, data, graph_start_time, axis_scaling, key):
        width, height = self._size.width, self._size.height
        scale = axis_scaling[key]['scale']

        def convert(datum):
            ts, val = datum[0], datum[1][key]
            return (MARGIN_X + (ts - graph_start_time) * SCALE_X,
                    height - MARGIN_BOTTOM - val * (height - MARGIN_TOP - MARGIN_BOTTOM) / scale)

        if len(data) < 2:
            return

        cr.move_to(*convert(data[0]))
        for d in data[1:]:
            cr.line_to(*convert(d))
        cr.set_source_rgb(*GRAPH_STYLE[key]['color'])
        cr.set_line_width(GRAPH_STYLE[key]['width'])
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.stroke()

class NetworkUsageWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self)
        self.init_frame()
        self.init_delete_event()
        self._prev_t = time.time()
        self._prev = poll_wifi_byte_counts()
        self._data = TimeIndexedData(300)
        GLib.timeout_add(POLLING_TIME_MILLISECONDS, self.on_timer)
        self._graph_view = GraphView(self._data)
        self.add(self._graph_view)

    def init_frame(self):
        self.set_default_size(800, 200)
        self.set_title('Network Usage')
        icon_filename = os.path.join(os.path.dirname(__file__), ICON_FILE_NAME)
        self.set_icon_from_file(icon_filename)

    def init_delete_event(self):
        self.connect('delete-event', Gtk.main_quit)
        accel = Gtk.AccelGroup()
        accel.connect(Gdk.keyval_from_name('Q'), Gdk.ModifierType.CONTROL_MASK, 0, Gtk.main_quit)
        self.add_accel_group(accel)

    def on_timer(self):
        curr_t = time.time()
        curr = poll_wifi_byte_counts()
        rate_recv = (curr[0] - self._prev[0]) / (curr_t - self._prev_t)
        rate_send = (curr[1] - self._prev[1]) / (curr_t - self._prev_t)
        self._prev_t = curr_t
        self._prev = curr
        self._data.add({'recv': rate_recv, 'send': rate_send})
        self._graph_view.queue_draw()
        return True

if __name__ == '__main__':
    netuse = NetworkUsageWindow()
    netuse.show_all()
    Gtk.main()

