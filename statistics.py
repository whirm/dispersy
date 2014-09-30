from abc import ABCMeta, abstractmethod
from collections import defaultdict
from threading import RLock
from time import time

from .util import _runtime_statistics, call_on_reactor_thread
from database import Database
from os import path
import logging
import random
from operator import itemgetter


class Statistics(object):

    __metaclass__ = ABCMeta

    def __init__(self):
        self._lock = RLock()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.db = None
        self._db_counter = dict()

    def dict_inc(self, dictionary, key, value=1):
        with self._lock:
            assert hasattr(self, "%s" % dictionary), u"%s doesn't exist in statistics" % dictionary
            if getattr(self, dictionary) is not None:
                getattr(self, dictionary)[key] += value

    def dict_inc_bartercast(self, stats_type, key, value=1):
        if not hasattr(self, "bartercast"):
                self._logger.error(u"bartercast doesn't exist in statistics")
        with self._lock:
            assert stats_type < len(self.bartercast), u"%s doesn't exist in bartercast statistics" % stats_type
            self.bartercast[stats_type][key] += value

    def get_top_n_bartercast_statistics(self, key, n):
        """
        Returns top n-n/2 barter cast statistics, +n/2 randomly selected statistics from the rest of the list.
        The randomly selected statistics are added to make sure that less active peers get a chance to appear in the rankings
        as well.
        @TODO check if random portion should be larger or smaller
        """
        with self._lock:
            # shouldn't happen but dont crash the program when bartercast statistics are not available
            if not hasattr(self, "bartercast"):
                self._logger.error(u"bartercast doesn't exist in statistics")
                return []
            if not key in getattr(self, "bartercast").keys():
                self._logger.error(u"%s doesn't exist in bartercast statistics" % key)
                return []
            d = getattr(self, "bartercast")[key]
            if d is not None:
                random_n = n / 2
                fixed_n = n - random_n
                sorted_list = sorted(d.items(), key=itemgetter(1), reverse=True)
                top_stats = sorted_list[0:fixed_n]
                self._logger.error("len d: %d, fixed_n: %d" % (len(d), fixed_n))
                if len(d) <= fixed_n:
                    random_stats = []
                else:
                    random_stats = random.sample(sorted_list[fixed_n:len(d)], min(random_n, len(d) - fixed_n))
                return top_stats + random_stats
            return None

    def get_dict(self):
        """
        Returns a deep clone of SELF as a dictionary.

        Warning: there is no recursion protection, if SELF contains self-references it will hang.
        """
        def clone(o):
            if isinstance(o, Statistics):
                return dict((key, clone(value))
                            for key, value
                            in o.__dict__.items()
                            if not key.startswith("_"))

            if isinstance(o, dict):
                return dict((clone(key), clone(value))
                            for key, value
                            in o.items())

            if isinstance(o, tuple):
                return tuple(clone(value) for value in o)

            if isinstance(o, list):
                return [clone(value) for value in o]

            return o
        return clone(self)

    @abstractmethod
    def update(self):
        pass

    def log_interaction(self, dispersy, type, peer1, peer2, value):
        """
        Add statistic for interactions between peer1 and peer2 to the interaction log.
        """
        self._init_database(dispersy)
        self.db.execute(u"INSERT INTO interaction_log (peer1, peer2, type, value, date) values (?, ?, ?, ?, strftime('%s', 'now'))", (unicode(peer1), unicode(peer2), type, value))

    def persist(self, dispersy, key, data, n=1):
        """
        Persists the statistical data with name 'key' in the statistics database.
        Note: performs the database update for every n-th call. This is to somewhat control the number of
        writes for statistics that are updated often.
        """
        if not self.should_persist(key, n):
            return

        self._init_database(dispersy)
#        pickle_object = cPickle.dumps(data)
        self._logger.error("persisting bc data")
#        self.db.execute(u"INSERT OR REPLACE INTO statistic (name, object) values (?, ?)", (unicode(key), unicode(pickle_object)))
        for t in data:
            for peer in data[t]:
                self.db.execute(u"INSERT OR REPLACE INTO statistic (type, peer, value) values (?, ?, ?)", (t, unicode(peer), data[t][peer]))
        self._logger.error("data persisted")

    def load_statistic(self, dispersy, key):
        self._init_database(dispersy)
        data = self.db.execute(u"SELECT type, peer, value FROM statistic")
        statistics = defaultdict()
        for t in BartercastStatisticTypes.reverse_mapping:
            statistics[t] = defaultdict()
        for row in data:
            t = row[0]
            peer = row[1]
            value = row[2]
            if not t in statistics:
                statistics[t] = defaultdict()
            statistics[t][peer] = value
        self._logger.error("statistics loaded: %s" % statistics)
        return statistics

#        data = self.db.execute(u"SELECT object FROM statistic WHERE name = ? LIMIT 1", [unicode(key)])
#        for row in data:
#            return cPickle.loads(str(row[0]))
#        return defaultdict()

    def _init_database(self, dispersy):
        if self.db is None:
            self.db = StatisticsDatabase(dispersy)
            self.db.open()

    def should_persist(self, key, n):
        """
        Return true and reset counter for key iff the data should be persisted (for every n calls).
        Otherwise increases the counter for key.
        """
        if key not in self._db_counter:
            self._db_counter[key] = 1
        else:
            self._db_counter[key] = self._db_counter[key] + 1
        if n <= self._db_counter[key]:
            self._db_counter[key] = 0
            return True
        return False


class MessageStatistics(object):

    def __init__(self):
        super(MessageStatistics, self).__init__()
        self._lock = RLock()

        self.total_received_count = 0
        self.success_count = 0
        self.drop_count = 0
        self.created_count = 0
        self.outgoing_count = 0

        self.delay_received_count = 0
        self.delay_send_count = 0
        self.delay_timeout_count = 0
        self.delay_success_count = 0

        self.success_dict = None
        self.drop_dict = None
        self.created_dict = None
        self.delay_dict = None
        self.outgoing_dict = None

        self._enabled = None

    def increase_count(self, category, name, value=1):
        with self._lock:
            count_name = u"%s_count" % category
            dict_name = u"%s_dict" % category
            if hasattr(self, count_name):
                setattr(self, count_name, getattr(self, count_name) + value)
            if getattr(self, dict_name) is not None:
                getattr(self, dict_name)[name] += value

    def increase_delay_count(self, category, value=1):
        with self._lock:
            count_name = u"delay_%s_count" % category
            setattr(self, count_name, getattr(self, count_name) + value)

    def enable(self, enabled):
        with self._lock:
            if self._enabled != enabled:
                self._enabled = enabled
                assigned_value = lambda: defaultdict(int) if enabled else None

                self.success_dict = assigned_value()
                self.outgoing_dict = assigned_value()
                self.created_dict = assigned_value()
                self.drop_dict = assigned_value()
                self.delay_dict = assigned_value()

    def reset(self):
        with self._lock:
            self.total_received_count = 0
            self.success_count = 0
            self.drop_count = 0
            self.created_count = 0
            self.outgoing_count = 0

            self.delay_received_count = 0
            self.delay_send_count = 0
            self.delay_timeout_count = 0
            self.delay_success_count = 0

            if self._enabled:
                self.success_dict.clear()
                self.drop_dict.clear()
                self.created_dict.clear()
                self.delay_dict.clear()
                self.outgoing_dict.clear()


class DispersyStatistics(Statistics):

    def __init__(self, dispersy, load_bartercast=True):
        super(DispersyStatistics, self).__init__()
        self._dispersy = dispersy

        self.communities = None
        self.start = self.timestamp = time()

        # nr of bytes up/down and packets send/received as reported by endpoint
        self.total_down = 0
        self.total_up = 0
        self.total_send = 0
        self.total_received = 0

        # size of the sendqueue
        self.cur_sendqueue = 0

        # nr of candidates introduced/stumbled upon
        self.total_candidates_discovered = 0

        # walk statistics
        self.walk_attempt_count = 0
        self.walk_success_count = 0
        self.walk_failure_count = 0
        self.walk_failure_dict = None
        self.invalid_response_identifier_count = 0

        self.incoming_intro_count = 0
        self.incoming_intro_dict = None
        self.outgoing_intro_count = 0
        self.outgoing_intro_dict = None

        self.attachment = None
        self.endpoint_recv = None
        self.endpoint_send = None
        self.received_introductions = None

        # list with {count=int, duration=float, average=float, entry=str} dictionaries.  each entry
        # represents a key from the attach_runtime_statistics decorator
        self.runtime = None

        self._enabled = None
        self.msg_statistics = MessageStatistics()
        self.enable_debug_statistics(__debug__)

        self.update()

        if load_bartercast:
            self.load_bartercast()
        else:
            self.bartercast = defaultdict()

    @call_on_reactor_thread
    def load_bartercast(self):
        self._logger.error("loading bartercast statistics:")
        self.bartercast = self.load_statistic(self._dispersy, u"bartercast")
        self._logger.error(self.bartercast)

    @property
    def database_version(self):
        return self._dispersy.database.database_version

    @property
    def lan_address(self):
        return self._dispersy.lan_address

    @property
    def wan_address(self):
        return self._dispersy.wan_address

    @property
    def connection_type(self):
        return self._dispersy.connection_type

    def enable_debug_statistics(self, enable):
        if self._enabled != enable:
            self._enabled = enable
            self.msg_statistics.enable(enable)

            dict_assigned_value = lambda: defaultdict(int) if enable else None
            self.walk_failure_dict = dict_assigned_value()
            self.incoming_intro_dict = dict_assigned_value()
            self.outgoing_intro_dict = dict_assigned_value()

            self.attachment = dict_assigned_value()
            self.endpoint_recv = dict_assigned_value()
            self.endpoint_send = dict_assigned_value()

            # SOURCE:INTRODUCED:COUNT nested dictionary
            self.received_introductions = defaultdict(lambda: defaultdict(int)) if enable else None

            for community in self._dispersy.get_communities():
                community.statistics.enable_debug_statistics(enable)

    def are_debug_statistics_enabled(self):
        return self._enabled

    def update(self, database=False):
        self.timestamp = time()

        self.communities = [community.statistics for community in self._dispersy.get_communities()]
        for community in self.communities:
            community.update(database=database)

        # list with {count=int, duration=float, average=float, entry=str} dictionaries.  each entry
        # represents a key from the attach_runtime_statistics decorator
        self.runtime = [(statistic.duration, statistic.get_dict(entry=entry)) for entry, statistic in _runtime_statistics.iteritems() if statistic.duration > 1]
        self.runtime.sort(reverse=True)
        self.runtime = [statistic[1] for statistic in self.runtime]

    def reset(self):
        self.total_down = 0
        self.total_up = 0
        self.total_send = 0
        self.total_received = 0
        self.cur_sendqueue = 0
        self.start = self.timestamp = time()

        # walk statistics
        self.walk_attempt_count = 0
        self.walk_success_count = 0
        self.walk_failure_count = 0
        self.walk_failure_dict = None
        self.invalid_response_identifier_count = 0

        self.incoming_intro_count = 0
        self.incoming_intro_dict = None
        self.outgoing_intro_count = 0
        self.outgoing_intro_dict = None

        self.msg_statistics.reset()

        if self.are_debug_statistics_enabled():
            self.walk_failure_dict = defaultdict(int)
            self.incoming_intro_dict = defaultdict(int)
            self.outgoing_intro_dict = defaultdict(int)

            self.attachment = defaultdict(int)
            self.endpoint_recv = defaultdict(int)
            self.endpoint_send = defaultdict(int)
            self.received_introductions = defaultdict(lambda: defaultdict(int))


class CommunityStatistics(Statistics):

    def __init__(self, community):
        super(CommunityStatistics, self).__init__()

        self._dispersy = community.dispersy
        self._community = community
        self.database_id = community.database_id
        self.classification = community.get_classification()
        self.cid = community.cid
        self.mid = community.my_member.mid
        self.hex_cid = community.cid.encode("HEX")
        self.hex_mid = community.my_member.mid.encode("HEX")

        self.database = dict()

        self.total_candidates_discovered = 0

        self.msg_statistics = MessageStatistics()

        self.sync_bloom_new = 0
        self.sync_bloom_reuse = 0
        self.sync_bloom_send = 0
        self.sync_bloom_skip = 0

        self.dispersy_acceptable_global_time_range = self._community.dispersy_acceptable_global_time_range

        self.dispersy_enable_candidate_walker = self._community.dispersy_enable_candidate_walker
        self.dispersy_enable_candidate_walker_responses = self._community.dispersy_enable_candidate_walker_responses

        self.enable_debug_statistics(self._dispersy.statistics.are_debug_statistics_enabled())

        self.bartercast = defaultdict()
        for t in BartercastStatisticTypes.reverse_mapping:
            self.bartercast[t] = defaultdict(int)

    def increase_total_received_count(self, value):
        self.msg_statistics.total_received_count += value

    def increase_discovered_candidates(self, value=1):
        self.total_candidates_discovered += value
        self._dispersy.statistics.total_candidates_discovered += value

    def increase_msg_count(self, category, name, value=1):
        self.msg_statistics.increase_count(category, name, value)
        self._dispersy.statistics.msg_statistics.increase_count(category, name, value)

    def increase_delay_msg_count(self, category, value=1):
        self.msg_statistics.increase_delay_count(category, value)
        self._dispersy.statistics.msg_statistics.increase_delay_count(category, value)

    # @TODO anonymize this using bucket?
    def increase_tunnel_stats(self, stats_type, peer, value=1):
        self.bartercast[stats_type][peer] += value

    @property
    def acceptable_global_time(self):
        return self._community.acceptable_global_time

    @property
    def global_time(self):
        return self._community.global_time

    @property
    def candidates(self):
        now = time()
        return [(candidate.lan_address, candidate.wan_address, candidate.global_time,
                 candidate.get_member().mid if candidate.get_member() else None)
                for candidate in self._community.candidates.itervalues()
                if candidate.get_category(now) in [u'walk', u'stumble', u'intro']]

    def enable_debug_statistics(self, enabled):
        self.msg_statistics.enable(enabled)

    def update(self, database=False):
        if database:
            self.database = dict(self._community.dispersy.database.execute(u"SELECT meta_message.name, COUNT(sync.id) FROM sync JOIN meta_message ON meta_message.id = sync.meta_message WHERE sync.community = ? GROUP BY sync.meta_message", (self._community.database_id,)))
        else:
            self.database = dict()

    def reset(self):
        self.total_candidates_discovered = 0
        self.msg_statistics.reset()

class RuntimeStatistic(object):

    def __init__(self):
        self._count = 0
        self._duration = 0.0

    @property
    def count(self):
        " Returns the number of times a method was called. "
        return self._count

    @property
    def duration(self):
        " Returns the cumulative time spent in a method. "
        return self._duration

    @property
    def average(self):
        " Returns the average time spent in a method. "
        return self._duration / self._count

    def increment(self, duration):
        " Increase self.count with 1 and self.duration with DURATION. "
        assert isinstance(duration, float), type(duration)
        self._duration += duration
        self._count += 1

    def get_dict(self, **kargs):
        " Returns a dictionary with the statistics. "
        return dict(count=self.count, duration=self.duration, average=self.average, **kargs)

_runtime_statistics = defaultdict(RuntimeStatistic)

LATEST_VERSION = 1

# old
# -- statistic contains a dump of the pickle object of a statistic. Mainly used to backup bartercast statistics.
# CREATE TABLE statistic(
# id INTEGER,                            -- primary key
# name TEXT,                             -- name of the statistic
# object TEXT,                           -- pickle object representing the statistic
# PRIMARY KEY (id),
# UNIQUE (name));

schema = u"""
CREATE TABLE statistic(
 id INTEGER,                            -- primary key
 type INTEGER,                            -- type of interaction
 peer TEXT,
 value INTEGER,
 PRIMARY KEY (id),
 UNIQUE (type, peer));

CREATE TABLE option(key TEXT PRIMARY KEY, value BLOB);
INSERT INTO option(key, value) VALUES('database_version', '""" + str(LATEST_VERSION) + """');

CREATE TABLE interaction_log(
 id INTEGER,                            -- primary key
 peer1 TEXT,
 peer2 TEXT,
 type INTEGER,                        -- type of interaction
 value INTEGER,
 date INTEGER,
 PRIMARY KEY (id));
"""

cleanup = u"""
DELETE FROM statistic;
"""


class StatisticsDatabase(Database):
    if __debug__:
        __doc__ = schema

    def __init__(self, dispersy):
        self._dispersy = dispersy
        super(StatisticsDatabase, self).__init__(path.join(dispersy.working_directory, u"sqlite", u"statistics.db"))

    def open(self):
        self._dispersy.database.attach_commit_callback(self.commit)
        return super(StatisticsDatabase, self).open()

    def close(self, commit=True):
        self._dispersy.database.detach_commit_callback(self.commit)
        return super(StatisticsDatabase, self).close(commit)

    def cleanup(self):
        self.executescript(cleanup)

    def check_database(self, database_version):
        assert isinstance(database_version, unicode)
        assert database_version.isdigit()
        assert int(database_version) >= 0
        database_version = int(database_version)

        # setup new database with current database_version
        if database_version < 1:
            self.executescript(schema)
            self.commit()

        else:
            # upgrade to version 2
            if database_version < 2:
                # there is no version 2 yet...
                # if __debug__: dprint("upgrade database ", database_version, " -> ", 2)
                # self.executescript(u"""UPDATE option SET value = '2' WHERE key = 'database_version';""")
                # self.commit()
                # if __debug__: dprint("upgrade database ", database_version, " -> ", 2, " (done)")
                pass

        return LATEST_VERSION


def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    reverse = dict((value, key) for key, value in enums.iteritems())
    enums['reverse_mapping'] = reverse
    return type('Enum', (), enums)

BartercastStatisticTypes = enum(TORRENTS_RECEIVED=1, TUNNELS_CREATED=2, \
                                TUNNELS_BYTES_SENT=3, TUNNELS_RELAY_BYTES_SENT=4, TUNNELS_EXIT_BYTES_SENT=5, \
                                TUNNELS_BYTES_RECEIVED=6, TUNNELS_RELAY_BYTES_RECEIVED=7, TUNNELS_EXIT_BYTES_RECEIVED=8)
