# igscraper/models/__init__.py

"""
Initialize model registry by importing all decorated models.
This ensures ENTRIES is populated before GraphQLModelRegistry runs.
"""

from .common import ENTRIES, register_model, BaseFlexibleSafeModel

# Import all modules that declare @register_model classes.
# ⚠️ Don't use "import *" — we just need to trigger module import so decorators run.

from .timeline import UserTimelineGraphQLConnection
from .shortcode import ShortcodeData
from .comments import CommentsData
from .v1_feed_user_timeline import RootResponse

# add more as you create new model modules

__all__ = [
    "ENTRIES",
    "register_model",
    "BaseFlexibleSafeModel",
    "UserTimelineGraphQLConnection",
    "ShortcodeData",
    "CommentsData",
    "RootResponse"
]

# class RootResponse(BaseFlexibleSafeModel):
#     # data can be any of the supported API shapes
#     data: Optional[TimelineData | ShortcodeData | CommentsData]
#     extensions: Optional[Extensions]
#     status: Optional[str]
