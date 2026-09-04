from uuid import uuid4
from textwrap import dedent

from omegaml.store import MongoQueryOps


class EpisodeMemory:
    def __init__(self, dataset=None, data_store=None):
        self._dataset = dataset
        self.data_store = data_store

    def __repr__(self):
        dataset = self.dataset
        return f'EpisodeMemory({dataset=})'

    @property
    def dataset(self):
        self._dataset = (self._dataset or uuid4().hex).replace('memory/', '', 1)
        return f'memory/{self._dataset}'

    def memory_tool(self, op, scope, title=None, item=None, tags=None):
        """The memory tool to store, list and retrieve remembered facts

        Args:
            op (str): the operation, one of add, get, list, wipe
            scope (str): 'sessionid' to store for this session, 'agent' to store across sessions, optional for
               op=get|list
            title (str): the descriptive title for this item, use with op=add|get|list, optional for get, list
            item (str): the fact to store, use with op=add
            tags (str): tags to remember facts by, use keywords from the title, use with op=get|list,
              separate multiple tags by comma, optional for get, list
        """
        tags = [t.lower() for t in str(tags).split(',')] if tags else (title.split() if title else [])
        if op == 'add':
            return self.add_to_memory(scope=scope, title=title, item=item, tags=tags)
        elif op == 'get':
            return self.get_from_memory(scope=scope, title=title, tags=tags)
        elif op == 'list':
            return self.list_memory(scope=scope, title=title, tags=tags)
        elif op == 'wipe':
            return self.wipe_memory(scope=scope, tags=tags)

    def add_to_memory(self, scope, title, item, tags):
        """store some knowledge item to session or agent storage

        Args:
            scope (str): 'sessionid' to store for this session, 'agent' to store across sessions
            title (str): the descriptive title for this item
            item (str): the fulltext data to store
            tags (list): list of tags

        Returns:
            None
        """
        self.data_store.put({'scope': scope, 'title': title, 'data': item, 'tags': tags}, self.dataset)

    def get_from_memory(self, scope=None, title=None, tags=None):
        """retrieve some item from memory

        Args:
            scope (str): 'sessionid' to store for this session, 'agent' to store across sessions
            title (str): the descriptive title for this item
            tags (list): optional, list of tags

        Returns:
            str: the item
        """
        x = MongoQueryOps()
        filter = {}
        filter.update({'data.scope': scope}) if scope else None
        filter.update({'data.title': x.CONTAINS(title)}) if title else None
        filter.update({'data.tags': x.IN(tags)}) if tags else None
        return self.data_store.get(self.dataset, filter=filter)

    def list_memory(self, scope=None, title=None, tags=None):
        """list memory entries

        Args:
            scope (str): 'sessionid' to store for this session, 'agent' to store across sessions
            title (str): the descriptive title for this item
            tags (list): optional, list of tags

        Returns:
            list[dict]: the list of entries as dicts
        """
        x = MongoQueryOps()
        filter = {}
        filter.update({'data.scope': scope}) if scope else None
        filter.update({'data.title': x.CONTAINS(title)}) if title else None
        filter.update({'data.tags': x.IN(tags)}) if tags else None
        data = self.data_store.get(self.dataset, filter=filter) or []
        return [entry for entry in data]

    def memory_prompt(self):
        text = dedent("""
        List of remembered items in memory (scope, title):
        """)
        memory = ((entry.get('scope'), entry.get('title')) for entry in self.list_memory())
        items = '\n'.join(f'* {scope=} {title=}' for scope, title in memory)
        return dedent(text + items)

    def wipe_memory(self, scope, title=None, tags=None):
        x = MongoQueryOps()
        filter = {'data.scope': scope} if scope else None
        filter.update({'data.scope': scope}) if scope else None
        filter.update({'data.title': x.CONTAINS(title)}) if title else None
        filter.update({'data.tags': x.IN(tags)}) if tags else None
        self.data_store.collection(self.dataset).delete_many(filter)
