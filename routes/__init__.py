"""The platform's routes. Requests to its APIs are limited per client address, with Flask-Limiter."""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# The counts are kept in memory: the platform runs one worker.
limiter = Limiter(get_remote_address, storage_uri="memory://")
