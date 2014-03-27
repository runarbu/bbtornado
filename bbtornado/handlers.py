import os
import tornado.web

from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import scoped_session

def authenticated(error_code=401, error_message="Not Found"):
    """Decorate methods with this to require that the user be logged in.
    If the user is not logged in, error_code will be set and error_message returned
    """
    def decorator(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            if not self.current_user:
                raise tornado.web.HTTPError(error_code, log_message=error_message)
            return method(self, *args, **kwargs)
        return wrapper
    return decorator

class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        if not hasattr(self, '_session'):
            self._session = scoped_session(self.application.Session)
        return self._session

    def on_finish(self):
        if hasattr(self, '_session'):
            self._session.remove()

    def get_current_user(self):
        user_id = self.get_secure_cookie('user_id')
        if self.application.user_model is not None:
            return self.db.query(self.application.user_model).get(int(user_id)) if user_id else None
        else:
            return int(user_id) if user_id else None

    @tornado.web.RequestHandler.current_user.setter
    def current_user(self, value):
        if self.application.user_model is not None and isinstance(value, self.application.user_model):
            value = value.id
        self.set_secure_cookie('user_id', unicode(value))

    @property
    def executor(self):
        return self.get_executor()

    _default_executor = ThreadPoolExecutor(10)
    def get_executor(self):
        return self._default_executor

class SingleFileHandler(tornado.web.StaticFileHandler):
    def initialize(self,filename):
        path, self.filename = os.path.split(filename)
        return super(SingleFileHandler, self).initialize(path)
    def get(self, *args, **kwargs):
        return super(SingleFileHandler, self).get(self.filename)
