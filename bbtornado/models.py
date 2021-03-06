"""
Utilities for SQLAlchemy models.

Mainly code for json serialisation, and protected/private fields that should not be serialised
"""

import sqlalchemy.orm

from datetime import datetime, date
from decimal import Decimal

from sqlalchemy.orm.query import Query
from sqlalchemy.orm.session import Session
from sqlalchemy.ext.declarative import declarative_base

import uuid
import json


Base = declarative_base()

class RestJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if hasattr(o, '_to_json'):
            return o._to_json()
        if isinstance(o, Decimal): return float(o)
        if isinstance(o, (datetime, date)): return o.isoformat()
        return json.JSONEncoder.default(self, o)

def register_json_decoder():
    json._default_encoder = RestJSONEncoder()

def _to_json(o, *args, **kwargs):
    if isinstance(o, dict):
        o = {k: _to_json(v, *args, **kwargs) for k,v in o.items()}
    elif isinstance(o, (list, tuple)):
        o = [_to_json(v, *args, **kwargs) for v in o]
    elif isinstance(o, Query):
        rval = []
        for v in o:
            rval.append(_to_json(v, *args, **kwargs))
        o = rval
    elif hasattr(o, '_to_json'):
        o = o._to_json(*args, **kwargs)
    elif isinstance(o, Decimal):
        o = float(o)
    elif isinstance(o, datetime):
        if not o.tzinfo:
            o = o.isoformat()+'Z'
        else:
            o = o.isoformat()
    elif isinstance(o, date):
        o = o.isoformat()
    elif isinstance(o, uuid.UUID):
        o = o.hex

    return o

class BaseModel(object):

    @property
    def session(self):
        return Session.object_session(self)


    def _to_json(self, private=False, extra_fields=[], skip_nulls=False):

        """
        Render this object as a json dict

        set `private=True` to include private fields

        `extra_fields` is a collection of other fields to include/exclude:

        * [ 'users' ] will include the `users` field
        * [ 'users', 'users.team' ] will include the `users` field, and the `team` field for each user
        * [ 'users', 'users.!password' ] will include the `users` field, but NOT the password field for each user
        * [ 'users', 'users.^id' ] will include ONLY the id field of each user.

        extra_fields will also show private fields, hidden fields are never shown.

        If you specify a single ^/only field for sub-thing and it's a list, the list will only be that
        field value, not an object, i.e. `users.^id` will give you a list of just user IDs

        """

        fields = { p.key for p in sqlalchemy.orm.object_mapper(self).iterate_properties }
        fields.update(f for f in self._json_fields_public)

        if not private:
            fields.difference_update( self._json_fields_private )

        fields.update(f for f in extra_fields if '.' not in f and f[0] not in ('!^'))
        fields.difference_update( f[1:] for f in extra_fields if f.startswith('!') )

        fields.difference_update( self._json_fields_hidden )

        only_fields = [ f[1:] for f in extra_fields if f.startswith('^') ]
        if only_fields:
            fields.intersection_update(only_fields)

        rval = {}
        for k in fields:

            next_fields = { f[f.index('.')+1:] for f in extra_fields if '.' in f and f.startswith(k) }
            only_fields = [ f for f in next_fields if f.startswith('^') ]

            val = getattr(self, k)

            if len(only_fields) == 1 and isinstance(val, (list, tuple)):
                rval[k] = [ getattr(v, only_fields[0][1:]) for v in val ]
            else:

                rval[k] = _to_json(val,
                                   private=private,
                                   extra_fields=next_fields,
                                   skip_nulls=skip_nulls
                )

            if skip_nulls and rval[k] is None : del rval[k]

        return rval

    _json_fields_public = []
    _json_fields_private = []
    _json_fields_hidden = []

def init_db(engine=None):
    Base.metadata.create_all(bind=engine)

def drop_db(engine=None):
    Base.metadata.drop_all(bind=engine)
