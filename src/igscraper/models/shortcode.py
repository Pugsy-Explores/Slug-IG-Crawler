from typing import Optional, List, Dict
from .common import BaseFlexibleSafeModel, Caption, ImageVersions2, VideoVersion, Owner, User,register_model

# xdt_api__v1__media__shortcode__web_info
class ShortcodeMediaItem(BaseFlexibleSafeModel):
    id: Optional[str] = None
    pk: Optional[str] = None
    code: Optional[str] = None
    taken_at: Optional[int] = None
    media_type: Optional[int] = None
    product_type: Optional[str] = None

    like_count: Optional[int] = None
    view_count: Optional[int] = None
    comment_count: Optional[int] = None
    fb_comment_count: Optional[int] = None
    fb_like_count: Optional[int] = None

    caption: Optional[Caption] = None
    caption_is_edited: Optional[bool] = None
    image_versions2: Optional[ImageVersions2] = None
    video_versions: Optional[List[VideoVersion]] = []
    video_dash_manifest: Optional[str] = None

    owner: Optional[Owner] = None
    user: Optional[User] = None

    accessibility_caption: Optional[str] = None
    preview: Optional[str] = None
    preview_comments: Optional[List[Dict]] = []


class ShortcodeWebInfo(BaseFlexibleSafeModel):
    items: Optional[List[ShortcodeMediaItem]] = []


# @register_model("xdt_api__v1__media__shortcode__web_info")
class ShortcodeData(BaseFlexibleSafeModel):
    xdt_api__v1__media__shortcode__web_info: Optional[ShortcodeWebInfo] = None
