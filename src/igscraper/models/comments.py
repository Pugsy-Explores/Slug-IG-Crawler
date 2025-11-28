from typing import Optional, List, Union
from .common import BaseFlexibleSafeModel, User,register_model,SimpleGiphyMediaInfo


# --- Comment Node ---
class CommentNode(BaseFlexibleSafeModel):
    __typename: Optional[str] = None
    pk: Optional[Union[int,str]] = None
    text: Optional[str] = None
    created_at: Optional[Union[int,str]] = None

    child_comment_count: Optional[Union[int,str]] = None
    comment_like_count: Optional[Union[int,str]] = None
    # has_liked_comment: Optional[bool] = None
    has_translation: Optional[bool] = None

    # is_covered: Optional[bool] = None
    restricted_status: Optional[Union[int,str]] = None
    parent_comment_id: Optional[Union[int,str]] = None

    giphy_media_info: Optional[SimpleGiphyMediaInfo] = None

    user: Optional[User] = None


# --- Edge ---
class CommentEdge(BaseFlexibleSafeModel):
    cursor: Optional[str] = None
    node: Optional[CommentNode] = None


# --- Page Info ---
class CommentPageInfo(BaseFlexibleSafeModel):
    end_cursor: Optional[str] = None
    has_next_page: Optional[bool] = None
    has_previous_page: Optional[bool] = None
    start_cursor: Optional[str] = None


# --- Comments Connection ---
class CommentsConnection(BaseFlexibleSafeModel):
    edges: Optional[List[CommentEdge]] = None
    page_info: Optional[CommentPageInfo] = None


# --- Data wrapper ---
# @register_model("xdt_api__v1__media__media_id__comments__connection", consume=True)
class CommentsData(BaseFlexibleSafeModel):
    xdt_api__v1__media__media_id__comments__connection: Optional[CommentsConnection] = None