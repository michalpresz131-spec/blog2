from collections.abc import Mapping
from itertools import tee
import re

from turso_serverless import Cursor


_FORMAT_QMARK_REGEX = re.compile(r"(?<!%)%s")


class TursoCursorWrapper(Cursor):
    def execute(self, query, params=None):
        if params is None:
            return super().execute(query)
        param_names = list(params) if isinstance(params, Mapping) else None
        return super().execute(self.convert_query(query, param_names), params)

    def executemany(self, query, param_list):
        peekable, param_list = tee(iter(param_list))
        params = next(peekable, None)
        if params and isinstance(params, Mapping):
            param_names = list(params)
        else:
            param_names = None
        query = self.convert_query(query, param_names)
        return super().executemany(query, param_list)

    @staticmethod
    def convert_query(query, param_names=None):
        if param_names is None:
            return _FORMAT_QMARK_REGEX.sub("?", query).replace("%%", "%")
        return query % {name: f":{name}" for name in param_names}
