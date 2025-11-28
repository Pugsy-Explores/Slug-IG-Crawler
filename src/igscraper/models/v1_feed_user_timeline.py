from typing import Optional, List, Dict
from pydantic import BaseModel, Extra
from igscraper.models.comments import CommentsConnection
from igscraper.models.common import BaseFlexibleSafeModel, Caption, ImageVersions2, User, VideoVersion, Owner, register_model, Extensions,XdtViewer,Status


# --- Page Info (for pagination) ---
class PageInfo(BaseFlexibleSafeModel):
    end_cursor: Optional[str] = None
    has_next_page: Optional[bool] = None


# --- Owner (user who posted) ---
class Owner(BaseFlexibleSafeModel):
    id: Optional[str] = None
    username: Optional[str] = None
    profile_pic_url: Optional[str] = None
    is_private: Optional[bool] = None
    is_verified: Optional[bool] = None


# # --- Image + Video ---
# class ImageCandidate(BaseFlexibleSafeModel):
#     url: Optional[str] = None
#     width: Optional[int] = None
#     height: Optional[int] = None


# class ImageVersions2(BaseFlexibleSafeModel):
#     candidates: Optional[List[ImageCandidate]]


# class VideoVersion(BaseFlexibleSafeModel):
#     url: Optional[str] = None
#     width: Optional[int] = None
#     height: Optional[int] = None
#     type: Optional[int] = None


# # --- Caption ---
# class Caption(BaseFlexibleSafeModel):
#     text: Optional[str] = None



class CarouselMediaNode(BaseFlexibleSafeModel):
    id: Optional[str] = None
    pk: Optional[str] = None
    # code: Optional[str] = None
    taken_at: Optional[int] = None
    product_type: Optional[str] = None
    media_type: Optional[int] = None
    image_versions2: Optional[ImageVersions2] = None
    video_versions: Optional[List[VideoVersion]] = []
    user: Optional[Owner] = None
    caption: Optional[Caption] = None
    comment_count: Optional[int] = None
    like_count: Optional[int] = None
    view_count: Optional[int] = None

    carousel_parent_id : Optional[str] = None


# --- Node (media post) ---
class Node(BaseFlexibleSafeModel):
    # Post identity
    code: Optional[str] = None
    id: Optional[str] = None
    pk: Optional[str] = None
    taken_at: Optional[int] = None
    media_type: Optional[int] = None

    # Engagement
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    view_count: Optional[int] = None
    
    # features
    comments_disabled: Optional[bool] = None
    like_and_view_counts_disabled: Optional[bool] = None

    # Content
    caption: Optional[Caption] = None
    image_versions2: Optional[ImageVersions2] = None
    video_versions: Optional[List[VideoVersion]] = []

    # Owner
    owner: Optional[Owner] = None

    #product type
    product_type: Optional[str] = None
    user: Optional[User] = None
    # media type
    media_type: Optional[int] = None
    
    #carousel media
    carousel_media_count: Optional[int] = None
    carousel_media: Optional[List[CarouselMediaNode]] = []


    # partnership
    is_paid_partnership: Optional[bool] = None
    sponsor_tags: Optional[List[Dict]] = []


# --- Edge ---
class Edge(BaseFlexibleSafeModel):
    node: Optional[Node] = None
    cursor: Optional[str] = None


# --- Timeline Connection ---
# @register_model([
#     r"xdt_api__v1__feed__user_timeline_graphql_connection.*",
#     r"xdt_api__v1__feed__timeline__connection.*",
#     r"xdt_api__v1__feed__.*timeline.*"
# ])




# Atomic fallback (timeline only)
# @register_model('xdt_api__v1__feed__timeline__connection',match_all=True)
class UserTimelineGraphQLConnection(BaseFlexibleSafeModel):
    edges: Optional[List[Edge]] = None
    page_info: Optional[PageInfo] = None


# --- Data ---
# Composite model (when BOTH keys exist)
# @register_model(
#     [r"xdt_api__v1__feed__.*timeline.*", r"xdt_viewer"],
#     match_all=True,
#     scope="whole",
#     priority=100,    # run first
#     consume=True     # eat keys so atomics don’t double-parse
# )
class Data(BaseFlexibleSafeModel):
    xdt_api__v1__feed__user_timeline_graphql_connection: Optional[UserTimelineGraphQLConnection] = None
    xdt_api__v1__media__media_id__comments__connection: Optional[CommentsConnection] = None

    xdt_viewer: Optional[XdtViewer] = None


# Data related to each post/reel on the profile page
# --- Root Response ---

@register_model(".*", scope="whole", priority=100, consume=True)
class RootResponse(BaseFlexibleSafeModel):
    data: Optional[Data] = None
    extensions: Optional[Extensions] = None
    status: Optional[str] = None
