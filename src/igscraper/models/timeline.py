from typing import Optional, List
from pydantic import BaseModel
from .common import BaseFlexibleSafeModel, Caption, ImageVersions2, VideoVersion, Owner,register_model,XdtViewer

# xdt_api__v1__feed__user_timeline_graphql_connection

class Node(BaseFlexibleSafeModel):
    id: Optional[str] = None
    pk: Optional[str] = None
    code: Optional[str] = None
    taken_at: Optional[int] = None
    media_type: Optional[int] = None

    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    view_count: Optional[int] = None

    caption: Optional[Caption] = None
    image_versions2: Optional[ImageVersions2] = None
    video_versions: Optional[List[VideoVersion]] = []

    owner: Optional[Owner] = None


class Edge(BaseFlexibleSafeModel):
    cursor: Optional[str] = None
    node: Optional[Node] = None


class PageInfo(BaseFlexibleSafeModel):
    end_cursor: Optional[str] = None
    has_next_page: Optional[bool] = None

class UserTimelineGraphQLConnection(BaseFlexibleSafeModel):
    edges: Optional[List[Edge]] = None
    page_info: Optional[PageInfo] = None


class ViewerUser(BaseFlexibleSafeModel):
    id: Optional[str] = None



# @register_model('xdt_api__v1__feed__timeline__connection',match_all=True)
class TimelineData(BaseFlexibleSafeModel):
    xdt_api__v1__feed__user_timeline_graphql_connection: Optional[UserTimelineGraphQLConnection] = None
    xdt_viewer: Optional[XdtViewer] = None