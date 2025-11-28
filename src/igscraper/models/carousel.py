from typing import List, Optional, Any, Dict
from datetime import datetime
from igscraper.models.common import BaseFlexibleSafeModel, register_model

class ImageCandidate(BaseFlexibleSafeModel):
    url: str = None
    height: int | str | None = None
    width: int | str | None = None

class ImageVersions2(BaseFlexibleSafeModel):
    candidates: List[ImageCandidate]

class User(BaseFlexibleSafeModel):
    pk: str
    username: str
    profile_pic_url: Optional[str] = None

class Caption(BaseFlexibleSafeModel):
    created_at: int
    pk: str
    text: str
    # Add other caption fields as needed

class CarouselMediaItem(BaseFlexibleSafeModel):
    """Model for individual items in a carousel"""
    # pk: str
    id: Optional[str] = None
    # code: Optional[str] = None
    # taken_at: Optional[int] = None
    # media_type: Optional[int] = Field(None, description="1: photo, 2: video, 8: carousel")
    image_versions2: Optional[ImageVersions2] = None
    # video_versions: Optional[List[Any]] = None
    # original_height: Optional[int] = None
    # original_width: Optional[int] = None
    # accessibility_caption: Optional[str] = None
    # # Carousel specific fields
    # carousel_parent_id: Optional[str] = None
    # carousel_media_count: Optional[int] = None
    # carousel_media: Optional[List['CarouselMediaItem']] = None  # Self-reference for nested carousels

@register_model("fetch__XDTMediaDict", consume=True)
class MediaNode(BaseFlexibleSafeModel):
    """Model for the main media node in timeline"""
    code: str = None
    pk: int |str  | None = None
    id : str | None = None
    taken_at: int |str  | None = None
    media_type: int | str | None = None
    product_type: Optional[str] = None
    
    # Media content
    image_versions2: Optional[ImageVersions2] = None
    carousel_media: Optional[List[CarouselMediaItem]] = None
    user: Optional[User] = None
    
    # # Counts
    # comment_count: int
    # like_count: int
    # has_liked: bool
    # like_and_view_counts_disabled: bool
    
    # # User info
    # user: User
    # owner: Optional[User] = None
    
    # # Caption and metadata
    # caption: Optional[Caption] = None
    # caption_is_edited: Optional[bool] = None
    # accessibility_caption: Optional[str] = None
    
    # # Carousel specific
    # carousel_parent_id: Optional[str] = None
    # carousel_media_count: Optional[int] = None
    
    # # Additional fields
    # ad_id: Optional[str] = None
    # boosted_status: Optional[str] = None
    # organic_tracking_token: Optional[str] = None
    # link: Optional[str] = None
    # is_paid_partnership: Optional[bool] = None
    # location: Optional[Any] = None
    # usertags: Optional[Any] = None
    
    # # Technical fields
    # original_height: int
    # original_width: int
    # __typename: Optional[str] = None


