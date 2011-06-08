# Copyright 2009-2011 Yelp
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
""" Delete old files in a path (by default files that are older than 30 days)
"""
from datetime import datetime, timedelta
import logging
from optparse import OptionParser

try:
    import boto.utils
except ImportError:
    boto = None

from mrjob.emr import EMRJobRunner, parse_s3_uri
from mrjob.util import log_to_stream

log = logging.getLogger('mrjob.tools.emr.s3_tmpwatch')

DEFAULT_TIME_OLD = '30d'

def main():
    option_parser = make_option_parser()
    options, args = option_parser.parse_args()

    if not args:
        option_parser.error('Please specify one or more URIs')

    # set up logging
    if not options.quiet:
        log_to_stream(name='mrjob', debug=options.verbose)
    # suppress No handlers could be found for logger "boto" message
    log_to_stream(name='boto', level=logging.CRITICAL)

    time_old = process_time(options.time)
   
    for path in args:
        S3_cleanup(path, time_old,
            conf_path=options.conf_path,
            dry_run=options.test)

def S3_cleanup(glob_path, time_old, dry_run=False, conf_path=None):
    """Delete all files older than *time_old* in *path*.
       If *dry_run* is ``True``, then just log the files that need to be 
       deleted without actually deleting them
       """
    runner = EMRJobRunner(conf_path=conf_path)
    s3_conn = runner.make_s3_conn()

    log.info('Deleting all files in %s that are older than %r days old' % (glob_path, time_old))
    
    for path in runner.ls(glob_path):
        bucket_name, key_name = parse_s3_uri(path)
        bucket = s3_conn.get_bucket(bucket_name)

        for key in bucket.list(key_name):
            last_modified = datetime.strptime(key.last_modified, boto.utils.ISO8601)
            last_modified = last_modified.replace(tzinfo=None)
            time_delta = datetime.now() - last_modified
            if time_delta > time_old:
                # Delete it
                log.info('Deleting %s; is %s old' % (key.name, str(time_delta)))
                if not dry_run:
                    key.delete()

def process_time(time):
    if time[-1] == 'm':
        return timedelta(minutes=int(time[:-1]))
    elif time[-1] == 'h':
        return timedelta(hours=int(time[:-1]))
    elif time[-1] == 'd':
        return timedelta(days=int(time[:-1]))
    else:
        return timedelta(hours=int(time))
    
def make_option_parser():
    usage = '%prog [options] [URI(s)]'
    description = 'Delete all files in a given URI that are older that a specified time.\n\nThe time parameter defines the threshold for removing files. If the file has not been accessed for *time*, the  file is removed. The time argument is a number with an optional single-character suffix specifying the units: m for minutes, h for hours, d for days.  If no suffix is specified, time is in hours.'
    option_parser = OptionParser(usage=usage, description=description)
    option_parser.add_option(
        '-v', '--verbose', dest='verbose', default=False,
        action='store_true',
        help='Print more messages')
    option_parser.add_option(
           '-q', '--quiet', dest='quiet', default=False,
           action='store_true',
           help="Don't print anything to stderr; just print deleted files to stdout")
    option_parser.add_option(
        '-c', '--conf-path', dest='conf_path', default=None,
        help='Path to alternate mrjob.conf file to read from')
    option_parser.add_option(
        '--no-conf', dest='conf_path', action='store_false',
        help="Don't load mrjob.conf even if it's available")
    option_parser.add_option(
        '-t', '--time', dest='time',
        default=DEFAULT_TIME_OLD, type='str',
        help='The time the file needs to be old before deleting it')
    option_parser.add_option(
        '--test', dest='test', default=False,
        action='store_true',
        help="Don't actually delete any files; just log that we would")

    return option_parser

if __name__ == '__main__':
    main()

