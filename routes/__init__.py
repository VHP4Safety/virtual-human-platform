"""Routes of the platform."""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# The counts are kept in memory, as the platform is run with one worker.
limiter = Limiter(get_remote_address, storage_uri="memory://")
