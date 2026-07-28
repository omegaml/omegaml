"""
Unique (idempotent) execution tracking for omegaml jobs.

This module provides functionality to ensure that a job runs at most once
for a given unique key. This is useful for preventing duplicate execution
of scheduled or manually triggered jobs.

Usage:
    # Specify unique on schedule
    om.jobs.schedule('myjob', run_at='daily', unique='today')

    # Check before running manually
    from omegaml.notebook.uniquejob import JobUniqueKey, job_has_executed, check_unique_key
    key = JobUniqueKey('myjob', 'run_today')
    if not check_unique_key(key):
        om.runtime.job('myjob').run()

Pattern Matching:
    The unique value can be a date word or strftime pattern:
    - Date words: 'today', 'yesterday', 'tomorrow', any weekday name, any month name
    - strftime patterns: '%Y-%m-%d', '%Y-%m', '%Y-W%V', etc.
"""
from __future__ import absolute_import

import datetime
from functools import lru_cache

# Precompute all supported date words to avoid re-parsing at runtime
_DATE_WORD_ALIASES = {}


@lru_cache(maxsize=1)
def _get_date_word_aliases():
    """Get all supported date word aliases (lazy-loaded, cached)"""
    global _DATE_WORD_ALIASES
    if not _DATE_WORD_ALIASES:
        aliases = {
            'today': '%Y-%m-%d',
            'yesterday': '%Y-%m-%d',
            'tomorrow': '%Y-%m-%d',

            # Weekdays (full and short)
            'monday': '%A', 'tuesday': '%A', 'wednesday': '%A', 'thursday': '%A',
            'friday': '%A', 'saturday': '%A', 'sunday': '%A',
            'mon': '%A', 'tue': '%A', 'wed': '%A', 'thu': '%A', 'fri': '%A',
            'sat': '%A', 'sun': '%A',
            'weekend': '%Y-%m-%d',

            # Months (full and short)
            'january': '%Y-%m', 'february': '%Y-%m', 'march': '%Y-%m', 'april': '%Y-%m',
            'may': '%Y-%m', 'june': '%Y-%m', 'july': '%Y-%m', 'august': '%Y-%m',
            'september': '%Y-%m', 'october': '%Y-%m', 'november': '%Y-%m', 'december': '%Y-%m',
            'jan': '%Y-%m', 'feb': '%Y-%m', 'mar': '%Y-%m', 'apr': '%Y-%m',
            'jun': '%Y-%m', 'jul': '%Y-%m', 'aug': '%Y-%m', 'sep': '%Y-%m',
            'oct': '%Y-%m', 'nov': '%Y-%m', 'dec': '%Y-%m',

            # Week-based patterns
            'this-week': '%Y-W%V',
            'last-week': '%Y-W%V',
            'next-week': '%Y-W%V',

            # Year
            'this-year': '%Y',
        }
        # Set the global for use by other modules (_DATE_WORD_ALIASES)
        _DATE_WORD_ALIASES = aliases
    return _DATE_WORD_ALIASES


def is_date_word(value):
    """Check if a value is a recognized date word"""
    aliases = _get_date_word_aliases()
    return isinstance(value, str) and value.lower() in aliases


def resolve_unique_key(job_name, unique_value):
    """
    Resolve a unique key specification for a job.

    Args:
        job_name (str): the job's name
        unique_value: Either:
            - A strftime format string like '%Y-%m-%d'
            - A date word like 'today', 'weekly' (which maps to weekday strftime)
            - A datetime pattern with strftime codes

    Returns:
        str: The resolved key value (e.g., '2026-01-15')

    Raises:
        ValueError: If the unique_value cannot be resolved
    """
    if not is_date_word(unique_value):
        # Use as-is - it's a direct strftime format or already resolved
        return _resolve_format(unique_value)

    aliases = _get_date_word_aliases()
    normalized = unique_value.lower()

    # Get the alias pattern
    if normalized in aliases:
        pattern = aliases[normalized]
    elif '%Y' in str(unique_value):
        # Already a valid strftime pattern
        return _resolve_format(str(unique_value))
    else:
        raise ValueError(
            f"Cannot resolve unique key '{unique_value}' for job '{job_name}'. "
            f"Try one of: 'today', 'yesterday', 'tomorrow', or a strftime format like '%Y-%m-%d'. "
            f"Supports weekday names, month names (full/short), and common patterns."
        )

    return _resolve_format(pattern, date_word=normalized)


def _resolve_format(format_str, date_word=None):
    """
    Resolve a format string to its current value.

    Special handling for date words within strftime:
    - When date_word is 'any of today|yesterday|tomorrow', %A returns the weekday name
    - Weekend pattern handles special logic
    """
    now = datetime.datetime.now()
    normalized = date_word.lower().lower() if isinstance(date_word, str) else None

    # Special handling for weekend
    if normalized == 'weekend' or format_str == '%Y-%m-%d':
        if normalized == 'weekend':
            weekday = now.weekday()
            if weekday < 5:  # Mon-Fri are weekdays
                next_monday = now + datetime.timedelta(days=7 - weekday)
                return (next_monday).strftime(format_str)
            # Already weekend, use today
        return now.strftime(format_str)

    # Handle %A format for specific days
    if '%A' in format_str:
        target_names = {
            'monday': ['Monday', 'MONDAY'],
            'tuesday': ['Tuesday', 'TUESDAY'],
            'wednesday': ['Wednesday', 'WEDNESDAY'],
            'thursday': ['Thursday', 'THURSDAY'],
            'friday': ['Friday', 'FRIDAY'],
            'saturday': ['Saturday', 'SATURDAY'],
            'sunday': ['Sunday', 'SUNDAY'],
        }
        if date_word and date_word.lower() in target_names:
            # Find the next occurrence of this weekday
            current_day = now.weekday()
            target_day = list(target_names.keys()).index(date_word.lower())

            if normalized == 'every day':  # Handle "today" as '%A' case
                return _resolve_format('%Y-%m-%d')

            days_ahead = (target_day - current_day) % 7
            if days_ahead == 0:
                next_occurrence = now
            else:
                next_occurrence = now + datetime.timedelta(days=days_ahead)

            return _resolve_format('%Y-%m-%d')  # Return date for uniqueness check

        # Default to %A as weekday name
        return str(now.strftime(format_str))

    # Handle other strftime patterns
    if '%V' in format_str:  # Week number
        iso_cal = now.isocalendar()
        return f"{iso_cal[0]}-W{iso_cal[1]:02d}"

    # General strftime
    return now.strftime(format_str)


class JobUniqueKey:
    """Represents a unique execution key for a specific job"""

    def __init__(self, job_name, unique_value):
        self.job_name = job_name
        self.unique_value = unique_value
        self.key = resolve_unique_key(job_name, unique_value)

    @property
    def collection_name(self):
        """MongoDB collection name for storing unique runs"""
        return f"unique_runs_{self.job_name.replace('/', '_')}"

    @property
    def doc_id(self):
        """Document ID for this unique run"""
        return self.key

    def __str__(self):
        return f"JobUniqueKey(job='{self.job_name}', key='{self.key}')"

    def __repr__(self):
        return self.__str__()


def job_has_executed(job_name, unique_value):
    """
    Check if a job has already executed for the given unique key.

    This is called before job execution to determine if it should run.

    Args:
        job_name (str): the name of the job
        unique_value (str): the unique key specification (e.g., 'today', '%Y-%m')

    Returns:
        tuple: (has_executed: bool, result_doc_id/None: str or None)
               If has_executed is True, result_doc_id identifies the previous execution.
    """
    try:
        # Lazy import to avoid circular deps and allow injection for testing
        from omegaml.store.mongodbshim import mongodb_shim
        from bson.objectid import ObjectId

        unique_key = JobUniqueKey(job_name, unique_value)
        collection_name = unique_key.collection_name
        doc_id = unique_key.doc_id

        db = mongodb_shim()
        # Check if we can access MongoDB (may not be available in all contexts)
        if db is None:
            return False, None

        collection = db['unique_runs'] if 'unique_runs' in db.list_collection_names() else None

        if collection is None:
            return False, None

        doc = collection.find_one({'_id': doc_id})
        if doc:
            return True, doc.get('_id')

        return False, None

    except Exception:
        # If anything goes wrong (no mongo, network issues, etc.), don't block execution
        return False, None


def register_unique_execution(job_name, unique_value, result_job=None):
    """
    Register that this job has executed for the given unique key.

    This should be called after successful job execution to prevent future runs
    with the same key within the current period.

    Args:
        job_name (str): the name of the job
        unique_value (str): the unique key specification
        result_job (str, optional): the results job name for reference
    """
    try:
        from omegaml.store.mongodbshim import mongodb_shim

        unique_key = JobUniqueKey(job_name, unique_value)
        doc_id = unique_key.doc_id
        now = datetime.datetime.now()

        db = mongodb_shim()
        if db is None:
            return

        collection = db['unique_runs']
        # Insert or update (upsert) the execution record
        collection.update_one(
            {'_id': doc_id},
            {
                '$set': {
                    '_id': doc_id,
                    'job_name': job_name,
                    'unique_key': unique_value,
                    'resolved_key': unique_key.key,
                    'last_run_at': now,
                    'result_job': result_job,
                }
            },
            upsert=True
        )

    except Exception:
        # If anything goes wrong, don't block execution flow
        pass


def cleanup_unique_keys(max_age_days=365):
    """
    Clean up old unique execution records.

    Args:
        max_age_days (int): maximum age in days before cleanup
    """
    try:
        from omegaml.store.mongodbshim import mongodb_shim

        db = mongodb_shim()
        if db is None:
            return

        cutoff = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
        for collection_name in db.list_collection_names():
            if collection_name.startswith('unique_runs'):
                collection = db[collection_name]
                # Delete records older than max_age_days for this job's collections
                try:
                    collection.delete_many({'last_run_at': {'$lt': cutoff}})
                except Exception:
                    pass

    except Exception:
        pass
