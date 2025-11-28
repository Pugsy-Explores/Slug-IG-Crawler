import os
import pdb
import re
import json
import time
import random
import traceback
import logging
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional, Type

import numpy as np
# from .config import Config
from selenium.webdriver import ActionChains
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
)

import random
import time
from typing import Optional, Tuple, List, Dict
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

from igscraper.logger import get_logger

logger = get_logger(__name__)


def random_delay(min_s: float, max_s: float) -> None:
    """
    Pauses execution for a random duration between a min and max value.

    Args:
        min_s: The minimum number of seconds to sleep.
        max_s: The maximum number of seconds to sleep.
    """
    sleep_time = human_delay(math.log(min_s), max_s)
    logger.debug(f"Sleeping for {sleep_time:.2f} seconds.")
    time.sleep(sleep_time)

def human_delay(base=1.0, max_value=4.0):
    sleep_time = min(max_value, np.random.lognormal(mean=base, sigma=0.4))
    return sleep_time

def normalize_hashtags(caption: str) -> list[str]:
    """
    Extracts all hashtags (e.g., #example) from a given string.

    Args:
        caption: The string to search for hashtags.

    Returns:
        A list of hashtag strings found in the caption.
    """
    return re.findall(r"#\w+", caption or '')

# def criteria_example(metadata: dict) -> bool:
#     """Example criteria function - include posts with more than 100 likes"""
#     return metadata.get('likes', 0) > 100

# def safe_write_jsonl(path: Path, data: dict) -> None:
#     with open(path, 'a', encoding='utf-8') as f:
#         f.write(json.dumps(data, ensure_ascii=False) + '\n')


def get_all_video_srcs(driver):
    js_code = """
    function collectAllVideoSrcs() {
      const srcSet = new Set();

      document.querySelectorAll("video").forEach(video => {
        if (video.src) {
          srcSet.add(video.src);
        }
        video.querySelectorAll("source").forEach(source => {
          if (source.src) {
            srcSet.add(source.src);
          }
        });
      });

      return Array.from(srcSet);
    }
    return collectAllVideoSrcs();
    """
    return driver.execute_script(js_code)


def scrape_carousel_images(driver, image_gather_func, min_wait=0.5, max_wait=2.2):
    """
    Scrapes all images from an Instagram carousel by repeatedly clicking the 'Next' button.

    This function simulates a user clicking through a multi-image post. After each
    click, it calls `image_gather_func` to extract data from the newly visible images.

    Args:
        driver: The Selenium WebDriver instance, positioned on a post page.
        image_gather_func: A function that takes the driver and returns a list of image data.
        min_wait: The minimum random delay (in seconds) between clicks.
        max_wait: The maximum random delay (in seconds) between clicks.

    Returns:
        A list of all image data dictionaries collected from the carousel.
    """
    logger.info("Starting carousel image scrape.")
    image_data = []
    seen_srcs = set()  # track unique 'src' values
    wait = WebDriverWait(driver, 5)  # shorter timeout for Next button
    actions = ActionChains(driver)
    steps = 0
    video_srcs = set()

    while True:
        # Grab current visible images and video elements
        new_items = image_gather_func(driver)
        new_video_srcs = get_all_video_srcs(driver)
        video_srcs.update(new_video_srcs)
        logger.debug(
            f"Step {steps}: Found {len(new_items)} potential images and "
            f"{len(new_video_srcs)} video sources. "
            f"Total unique video sources: {len(video_srcs)}."
        )

        # Filter for unique images based on 'src'
        added_count = 0
        for item in new_items:
            src = item.get("src")
            if src and src not in seen_srcs:
                seen_srcs.add(src)
                image_data.append(item)
                added_count += 1
        if added_count > 0:
            logger.debug(f"Added {added_count} new unique images. Total unique: {len(image_data)}.")

        try:
            # Look for Next button
            next_button = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label='Next']"))
            )
            logger.debug("'Next' button found.")
        except (TimeoutException, NoSuchElementException):
            logger.info(f"Reached end of carousel after {steps} steps. No 'Next' button found.")
            break

        # Try to click like a human
        if not human_like_click(driver, next_button, actions):
            logger.warning(f"Could not click 'Next' button at step {steps}, stopping.")
            break

        steps += 1
        time.sleep(random.uniform(min_wait, max_wait))
    logger.info(f"Finished carousel scrape. Found {len(image_data)} total unique images.")
    return image_data, list(video_srcs)


def get_all_post_images_data(driver):
    """
    Extracts unique image data from Instagram posts using the fallback
    ul._acay > li._acaz > img logic via JavaScript executed in the browser.
    Duplicates (based on src) are removed.

    Args:
        driver: Selenium WebDriver instance.

    Returns:
        List of dictionaries with unique image attributes.
    """
    js_code = """
    const allImages = [];
    const seenSrc = new Set();

    document.querySelectorAll('ul._acay').forEach(ul => {
        ul.querySelectorAll('li._acaz img').forEach(img => {
            const src = img.getAttribute('src');
            if (!seenSrc.has(src)) {
                seenSrc.add(src);
                allImages.push({
                    src: src,
                    alt: img.getAttribute('alt'),
                    title: img.getAttribute('title'),
                    aria_label: img.getAttribute('aria-label'),
                    text: img.innerText ? img.innerText.trim() : null
                });
            }
        });
    });

    return allImages;
    """
    return driver.execute_script(js_code)

def media_from_post(driver):
    """
    A wrapper function to extract media (images/videos) from a post.

    It first attempts to scrape media assuming it's a multi-image carousel post.
    If that returns no media, it falls back to a method for scraping a single image.

    Args:
        driver: The Selenium WebDriver instance.
    """
    ## try to extract multiple media if they exist
    media = scrape_carousel_images(driver, get_all_post_images_data)
    image_data, video_srcs = media
    video_data = []
    if len(video_srcs) > 0:
        logger.info(f"Extracted {len(video_srcs)} video sources from carousel.")
        video_data = get_top_mp4_groups_with_curl(driver, len(video_srcs))
    else:
        logger.debug("No video sources found in carousel.")
    if image_data == [] and video_data == []:
        logging.info("Trying to extract single media.")
        # grab the single media if it exists
        return get_first_img_attributes_in_div(driver), {}
    logging.info(f"Extracted {len(image_data)} images from carousel and {len(video_data)} videos.")
    return image_data, video_data


def get_instagram_post_images(driver):
    """
    Extracts all attributes of `<img>` tags within a post's main article.

    This function uses an efficient combination of XPath and JavaScript to find all
    image elements, extract their attributes, and deduplicate them based on the 'src'
    attribute to ensure each image is only recorded once.

    Args:
        driver: The Selenium WebDriver instance.
    """
    try:
        xp = "//article//ul[contains(@class,'_acay')]//li[contains(@class,'_acaz')]//img"
        imgs = driver.find_elements(By.XPATH, xp)

        if not imgs:
            return []

        # Pull all attributes in one shot
        img_attrs = driver.execute_script("""
            return arguments[0].map(el => {
                let items = {};
                for (let attr of el.attributes) {
                    items[attr.name] = attr.value;
                }
                return items;
            });
        """, imgs)

        # Dedup by src
        seen = set()
        unique_imgs = []
        for attrs in img_attrs:
            src = attrs.get("src")
            if src and src not in seen:
                seen.add(src)
                unique_imgs.append(attrs)

        return unique_imgs

    except Exception as e:
        import traceback
        traceback.print_exc()
        return []



# def extract_attributes_by_tag_in_section(
#     driver: WebDriver, 
#     target_tag_name: str = 'a', 
#     timeout: int = 10
# ) -> Optional[List[Dict[str, Any]]]:
#     """
#     Finds a specific <section> using a stable XPath, then finds all descendant
#     elements within that section that have the target tag, and extracts all
#     attributes + inner text.

#     Args:
#         driver: The Selenium WebDriver instance.
#         target_tag_name: The tag name of the descendant elements
#                          whose attributes and text should be extracted.
#         timeout: Max wait time for section to appear.

#     Returns:
#         A list of dicts, where each contains:
#             - element_index: Index of the element
#             - tag_name: The target tag
#             - attributes: Dict of all element attributes
#             - text: The visible text of the element
#         Returns None if the section is not found or an error occurs.
#         Returns [] if no matching elements are found.
#     """

#     stable_section_xpath = "//section[./div[contains(@class, 'html-div')]]"

#     try:
#         # 1. Wait for section to exist (fixes timing issues)
#         section_element = WebDriverWait(driver, timeout).until(
#             EC.presence_of_element_located((By.XPATH, stable_section_xpath))
#         )

#         # 2. Find all target tags within the section
#         elements_with_target_tag = section_element.find_elements(By.TAG_NAME, target_tag_name)

#         if not elements_with_target_tag:
#             print(f"No elements with tag '{target_tag_name}' found inside the section.")
#             return []

#         all_elements_data: List[Dict[str, Any]] = []

#         for i, element in enumerate(elements_with_target_tag):
#             # Get attributes via JS
#             attributes_dict = driver.execute_script(
#                 """
#                 let attributes = arguments[0].attributes;
#                 let obj = {};
#                 for (let i = 0; i < attributes.length; i++) {
#                     obj[attributes[i].name] = attributes[i].value;
#                 }
#                 return obj;
#                 """,
#                 element
#             )

#             # Also grab inner text
#             element_text = element.text.strip()

#             all_elements_data.append({
#                 "element_index": i,
#                 "tag_name": target_tag_name,
#                 "attributes": attributes_dict,
#                 "text": element_text
#             })

#         return all_elements_data

#     except NoSuchElementException:
#         print("Error: Could not find the section element using the stable XPath.")
#         return None
#     except Exception as e:
#         print(f"An unexpected error occurred: {e}")
#         return None


# def extract_elements_with_numbers_in_section(
#     driver: WebDriver, 
#     target_tag_name: str = 'a', 
#     timeout: int = 10
# ) -> Optional[List[Dict[str, Any]]]:
#     """
#     Finds a <section> using a stable XPath, then extracts only those descendant
#     elements of the given tag whose visible text contains numbers
#     (e.g. '98,501', '12345', 'random text 2,345 others').

#     Args:
#         driver: Selenium WebDriver instance.
#         target_tag_name: The tag name of descendant elements to extract (e.g. 'a').
#         timeout: Max wait time for section to appear.

#     Returns:
#         A list of dicts containing:
#             - element_index
#             - tag_name
#             - attributes
#             - text
#             - extracted_numbers: list of numbers found in text (as strings)
#         Only includes elements where text contains a number.
#         Returns [] if none found, None on error.
#     """

#     stable_section_xpath = "//section[./div[contains(@class, 'html-div')]]"
#     number_pattern = re.compile(r'\d{1,3}(?:,\d{3})*|\d+')  
#     # matches "98,501", "12345", "2,345", etc.

#     try:
#         # 1. Wait for section
#         section_element = WebDriverWait(driver, timeout).until(
#             EC.presence_of_element_located((By.XPATH, stable_section_xpath))
#         )

#         # 2. Find all target tags
#         elements_with_target_tag = section_element.find_elements(By.TAG_NAME, target_tag_name)

#         results: List[Dict[str, Any]] = []

#         for i, element in enumerate(elements_with_target_tag):
#             text = element.text.strip()
#             matches = number_pattern.findall(text)

#             if not matches:
#                 continue  # skip if no numbers inside text

#             attributes_dict = driver.execute_script(
#                 """
#                 let attributes = arguments[0].attributes;
#                 let obj = {};
#                 for (let i = 0; i < attributes.length; i++) {
#                     obj[attributes[i].name] = attributes[i].value;
#                 }
#                 return obj;
#                 """,
#                 element
#             )

#             results.append({
#                 "element_index": i,
#                 "tag_name": target_tag_name,
#                 "attributes": attributes_dict,
#                 "text": text,
#                 "extracted_numbers": matches  # list of number strings
#             })

#         return results

#     except NoSuchElementException:
#         print("Error: Could not find the section element using the stable XPath.")
#         return None
#     except Exception as e:
#         print(f"An unexpected error occurred: {e}")
#         return None



def human_like_click(driver, element, actions, retries=3):
    """
    Attempts to click an element in a human-like way, with retries and a JS fallback.

    This function first scrolls the element into view, moves the mouse over it,
    and then attempts a standard click. If the click is intercepted, it retries.
    As a last resort, it uses a direct JavaScript click.

    Args:
        driver: The Selenium WebDriver instance.
        element: The WebElement to be clicked.
        actions: An ActionChains instance.
        retries: The number of click attempts before falling back to JavaScript.
    """
    for attempt in range(retries):
        try:
            # Scroll into view
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(random.uniform(0.3, 0.7))

            # Move "cursor" (Selenium-simulated)
            actions.move_to_element(element).perform()
            time.sleep(random.uniform(0.2, 0.6))

            # Normal click
            element.click()
            return True
        except ElementClickInterceptedException:
            if attempt < retries - 1:
                # Small random wait and retry
                time.sleep(random.uniform(0.5, 1.2))
            else:
                # Final fallback → force JS click
                driver.execute_script("arguments[0].click();", element)
                return True
        except TimeoutException:
            return False
    return False


def extract_post_title_details(driver: WebDriver):
    """
    Extracts details from divs that likely contain post title, author, and timestamp.

    It uses a broad XPath to find "innermost" divs that contain either a `<time>`
    or `<a>` tag but do not have nested divs with the same properties. For each
    matching div, it extracts its attributes, text, and any nested image, link,
    or time elements.

    Args:
        driver: The Selenium WebDriver instance.
    """
    results = []
    # Select <div class="html-div"> with <time> OR <a> inside
    divs = driver.find_elements(
        "xpath", "//div[contains(@class, 'html-div')][.//time or .//a][not(.//div[contains(@class, 'html-div')])]"
    )

    for div in divs:
        div_data = {}

        # --- div attributes ---
        attrs = driver.execute_script(
            """
            let attrs = {};
            for (let attr of arguments[0].attributes) {
                attrs[attr.name] = attr.value;
            }
            return attrs;
            """,
            div,
        )
        div_data["div_attributes"] = attrs

        # --- visible text ---
        text = div.text.strip()
        if text:
            div_data["text"] = text

        # --- images ---
        imgs = div.find_elements("xpath", ".//img")
        if imgs:
            div_data["images"] = [
                {"src": img.get_attribute("src"), "alt": img.get_attribute("alt")}
                for img in imgs if img.get_attribute("src")
            ]

        # --- anchors ---
        anchors = div.find_elements("xpath", ".//a")
        if anchors:
            div_data["links"] = [
                {"href": a.get_attribute("href"), "text": a.text.strip()}
                for a in anchors if a.get_attribute("href")
            ]

        # --- times ---
        times = div.find_elements("xpath", ".//time")
        if times:
            div_data["times"] = [
                {"datetime": t.get_attribute("datetime"), "text": t.text.strip()}
                for t in times
            ]

        if div_data:
            results.append(div_data)

    return results


def cleanup_details(data):
    """
    Cleans and deduplicates the raw data extracted by `extract_post_title_details`.

    - Images are deduplicated by 'src', and all unique 'alt' texts are collected.
    - Links are deduplicated by 'href'.
    - Times are deduplicated by 'datetime'.

    Args:
        data: The list of dictionaries produced by `extract_post_title_details`.
    """
    cleaned = []

    for item in data:
        new_item = item.copy()

        # Dedup images by src
        if "images" in new_item:
            img_map = {}
            for img in new_item["images"]:
                src = img.get("src")
                if not src:
                    continue
                if src not in img_map:
                    img_map[src] = {"src": src, "alt": []}

                alt = img.get("alt")
                if alt and alt not in img_map[src]["alt"]:
                    img_map[src]["alt"].append(alt)

            # If alt has only one entry, simplify to string
            for val in img_map.values():
                if len(val["alt"]) == 0:
                    val.pop("alt")  # no alts
                elif len(val["alt"]) == 1:
                    val["alt"] = val["alt"][0]

            new_item["images"] = list(img_map.values())

        # Dedup links by href
        if "links" in new_item:
            link_map = {}
            for link in new_item["links"]:
                href = link.get("href")
                if not href:
                    continue
                if href not in link_map:
                    link_map[href] = {"href": href}
                text_val = link.get("text")
                if text_val and not link_map[href].get("text"):
                    link_map[href]["text"] = text_val
            new_item["links"] = list(link_map.values())

        # Dedup times by datetime or text
        if "times" in new_item:
            time_map = {}
            for t in new_item["times"]:
                key = t.get("datetime") or t.get("text")
                if not key:
                    continue
                if key not in time_map:
                    time_map[key] = {}
                if t.get("datetime"):
                    time_map[key]["datetime"] = t["datetime"]
                if t.get("text") and not time_map[key].get("text"):
                    time_map[key]["text"] = t["text"]
            new_item["times"] = list(time_map.values())

        cleaned.append(new_item)

    return cleaned

# ##This functions works end to end.
# ## scrolling works fine
# ## extraction works fine for all scrolled comments.
# def scrape_comments(driver, wait_selector="div.html-div", steps=100, timeout=10):
#     """
#     Scrape Instagram-like comments from a page using Selenium.
    
#     Args:
#         driver: Selenium WebDriver instance.
#         wait_selector: CSS selector to wait for before executing JS.
#         timeout: Maximum seconds to wait for the comment container.
        
#     Returns:
#         List of dicts: Each dict has 'handle', 'date', 'comment', 'likes'.
#     """
#     # Wait until at least one comment container is present
#     WebDriverWait(driver, timeout).until(
#         EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
#     )
#     # pdb.set_trace()
#     container_info = find_comment_container(driver)
#     logger.info(f"Found comment container: {container_info}")
#     steps = random.randint(int(steps * 0.8), int(steps * 1.2))
#     human_scroll(driver, container_info.get("selector"), steps=steps)
#     js_code = """
#     function parseComments() {
#         const results = [];
#         const seen = new Set();

#         const topDivs = document.querySelectorAll("div.html-div");

#         topDivs.forEach(topDiv => {
#             const profileDiv = topDiv.querySelector("div > div.html-div > div.html-div");
#             const commentDiv = Array.from(topDiv.querySelectorAll("div > div.html-div > div.html-div"))
#                 .find(div => !div.querySelector("span a, span time"));

#             if (!profileDiv || !commentDiv) return;

#             const data = { likes: null, handle: null, date: null, comment: null };

#             // --- Likes ---
#             const likeSpan = Array.from(topDiv.querySelectorAll("span"))
#                 .map(s => s.innerText && s.innerText.trim())
#                 .filter(Boolean)
#                 .find(t => /\\b\\d{1,3}(?:,\\d{3})*(?:\\.\\d+)?[kKmM]?\\s+likes?\\b/i.test(t));
#             if (likeSpan) data.likes = likeSpan;

#             // --- Handle & date ---
#             const spans = profileDiv.querySelectorAll("span");
#             spans.forEach(span => {
#                 const aTag = span.querySelector("a");
#                 if (aTag && !data.handle) data.handle = aTag.innerText.trim();
#                 const timeTag = span.querySelector("time");
#                 if (timeTag && !data.date) data.date = timeTag.innerText.trim();
#             });

#             // --- Comment ---
#             const text = commentDiv.innerText.trim();
#             if (text) data.comment = text;

#             // Only keep if comment and date exist
#             if (data.comment && data.date) {
#                 const key = (data.handle || "") + "::" + data.comment;
#                 if (!seen.has(key)) {
#                     seen.add(key);
#                     results.push(data);
#                 }
#             }
#         });

#         return results;
#     }

#     return parseComments();
#     """

#     # Execute JS in the browser context
#     return driver.execute_script(js_code)

def scrape_comments_with_gif(driver, config, wait_selector="div.html-div", timeout=10):
    """
    Orchestrates the scraping of comments from a post page.

    This function performs three main steps:
    1. Finds the scrollable container for comments using `find_comment_container`.
    2. Scrolls the container down to load more comments using `human_scroll`.
    3. Executes a JavaScript payload to parse all visible comments, extracting
       the handle, date, text, likes, and any associated images/GIFs.

    Args:
        driver: The Selenium WebDriver instance.
        config: The application's configuration object.
        wait_selector: A CSS selector to wait for before starting the process.
        timeout: The maximum time to wait for the `wait_selector`.
    """
    # Wait until at least one comment container is present
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
    )
    container_info = find_comment_container(driver)
    logger.info(f"Found comment container: {container_info}")
    # steps = 100
    steps = config.main.comment_scroll_steps
    steps = random.randint(int(steps * 0.8), int(steps * 1.2))
    human_scroll(driver, container_info.get("selector"), steps=steps,max_retries=config.main.comments_scroll_retries)
    logger.info(f"Completed scrolling {steps} steps. Fetching comments...")
    js_code_mod = """
    function parseComments() {
        const results = [];
        const seen = new Set();

        const topDivs = document.querySelectorAll("div.html-div");

        topDivs.forEach(topDiv => {
            const profileDiv = topDiv.querySelector("div > div.html-div > div.html-div");
            const commentDiv = Array.from(topDiv.querySelectorAll("div > div.html-div > div.html-div"))
                .find(div => !div.querySelector("span a, span time"));

            if (!profileDiv || !commentDiv) return;

            const data = { likes: null, handle: null, date: null, comment: null, commentImgs: [] };

            // --- Likes ---
            const likeSpan = Array.from(topDiv.querySelectorAll("span"))
                .map(s => s.innerText && s.innerText.trim())
                .filter(Boolean)
                .find(t => /\\b\\d{1,3}(?:,\\d{3})*(?:\\.\\d+)?[kKmM]?\\s+likes?\\b/i.test(t));
            if (likeSpan) data.likes = likeSpan;

            // --- Handle & date ---
            const spans = profileDiv.querySelectorAll("span");
            spans.forEach(span => {
                const aTag = span.querySelector("a");
                if (aTag && !data.handle) data.handle = aTag.innerText.trim();
                const timeTag = span.querySelector("time");
                if (timeTag && !data.date) data.date = timeTag.innerText.trim();
            });

            // --- Comment text ---
            const text = commentDiv.innerText.trim();
            if (text) data.comment = text;

            // --- Collect all images under topDiv that have exactly "class" and "src" ---
            const imgTags = topDiv.querySelectorAll("img");
            if (imgTags.length > 0) {
                data.commentImgs = Array.from(imgTags)
                    .filter(img => {
                        const attrs = Array.from(img.attributes).map(a => a.name);
                        return attrs.length === 2 && attrs.includes("class") && attrs.includes("src");
                    })
                    .map(img => img.src);
            }

            // Keep if:
            // 1. commentImgs is present (regardless of comment/date)
            // OR
            // 2. commentImgs is NOT present, but both date AND comment exist
            const hasImages = data.commentImgs.length > 0;
            const hasCommentAndDate = data.comment && data.date;
            
            if (hasImages || hasCommentAndDate) {
                const key = (data.handle || "") + "::" + (data.comment || "") + "::" + data.commentImgs.join(",");
                if (!seen.has(key)) {
                    seen.add(key);
                    results.push(data);
                }
            }
        });

        return results;
    }

    // Execute the function and return results
    return parseComments();
    """


    # Execute JS in the browser context
    return driver.execute_script(js_code_mod)


def get_section_with_highest_likes(driver, wait_selector="section", timeout=10):
    """
    Finds the <section> element with the highest like count on the page.

    This function executes a JavaScript snippet that iterates through all `<section>`
    elements, finds the one containing text related to "likes", parses the number,
    and returns the data for the section with the highest count.

    Args:
        driver: The Selenium WebDriver instance.
        wait_selector: A CSS selector to wait for before executing the script.
        timeout: The maximum time to wait for the `wait_selector`.
    """
    # Wait until at least one section is present
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
    )
    logger.debug("Finding section with highest likes...")
    js_code = """
    return (function() {
        function parseLikes(text) {
            let num = parseFloat(text.replace(/[^\\d.kKmM]/g, ""));
            if (/k/i.test(text)) num *= 1;
            else if (/m/i.test(text)) num *= 1000;
            return num;
        }

        let maxLikes = -1;
        let topSection = null;

        const sections = document.querySelectorAll("section");

        sections.forEach(section => {
            if (!section.querySelector("span") || !section.querySelector("a")) return;

            const likeSpan = Array.from(section.querySelectorAll("span"))
                .find(span => span.innerText && /like/i.test(span.innerText));

            if (!likeSpan) return;

            const likesText = likeSpan.innerText.trim();
            const likesNumber = parseLikes(likesText);

            if (likesNumber > maxLikes) {
                maxLikes = likesNumber;
                topSection = { likesText: likesText, likesNumber: likesNumber };
            }
        });

        return topSection;  // null if none found
    })();
    """

    return driver.execute_script(js_code)


def get_first_img_attributes_in_div(driver, wait_selector="div img", timeout=10):
    """
    Finds the first `<img>` tag that is likely to be the main post image.

    This function is typically used as a fallback for single-image posts. It executes
    a JavaScript snippet that searches for the first `<img>` inside a `<div>` that
    has `alt`, `crossorigin`, and `src` attributes, and returns all of its attributes.

    Args:
        driver: The Selenium WebDriver instance.
        wait_selector: A CSS selector to wait for before executing the script.
        timeout: The maximum time to wait for the `wait_selector`.
    """
    # Wait until at least one image under a div is present
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
    )

    js_code = """
    return (function() {
        const img = Array.from(document.querySelectorAll("div img"))
            .find(i => i.hasAttribute("alt") && i.hasAttribute("crossorigin") && i.hasAttribute("src"));

        if (!img) return null;

        const attrs = {};
        Array.from(img.attributes).forEach(attr => {
            attrs[attr.name] = attr.value;
        });

        return attrs;
    })();
    """

    return driver.execute_script(js_code)



## --- div   (main container)
##    --- h2
##        --- there can be more nested classes here
##         -- <a href="variable_1">
##    --- div
##       --- h1
##          --- there can be more nested classes here
##          --- text we want

# from selenium import webdriver
# ## the time attribute needs to be fixed, its null as of now.
# def extract_h1_data(driver):
#     """
#     Extracts all <h1> text under containers with <h2>, deduplicated by h1 class,
#     and also extracts all attributes from any '.time' element inside the container.
    
#     Args:
#         driver (selenium.webdriver): Selenium WebDriver instance
    
#     Returns:
#         List[dict]: List of dictionaries with keys:
#                     'h1Class', 'h2Text', 'h1Text', 'timeAttributes'
#     """
#     js_code = """
#     function getUniqueH1sWithTimeAttributes() {
#         const results = [];
#         const seenH1Classes = new Set();

#         const containers = document.querySelectorAll("div");

#         containers.forEach(container => {
#             const h2 = container.querySelector("h2");
#             if (!h2) return;

#             const h1 = container.querySelector(":scope > div h1");
#             if (!h1) return;

#             const h1Text = (h1.textContent || "").trim();
#             if (!h1Text) return;

#             const h1Class = h1.className || "";
#             if (seenH1Classes.has(h1Class)) return;
#             seenH1Classes.add(h1Class);

#             const timeEl = container.querySelector("h1 time");
#             let timeAttributes = null;
#             if (timeEl) {
#                 timeAttributes = {};
#                 for (const attr of timeEl.attributes) {
#                     timeAttributes[attr.name] = attr.value;
#                 }
#             }

#             results.push({
#                 h1Class: h1Class,
#                 h2Text: (h2.textContent || "").trim(),
#                 h1Text: h1Text,
#                 timeAttributes: timeAttributes
#             });
#         });

#         return results;
#     }

#     return getUniqueH1sWithTimeAttributes();
#     """
#     # Execute the JS in the context of the page
#     return driver.execute_script(js_code)



# **Pseudo Logic:**

# 1. **Get all div elements** on the page.
# 2. **Loop through each div**:
#    a. Check if it contains an `<a>` element with `href = handle_name`.
#    b. Check if it contains a `<time>` element.
# 3. **Filter out divs that are not innermost**:

#    * For each candidate div, check if any **child div** also contains both `<a>` and `<time>`.
#    * If yes, skip this div; if no, mark it as the innermost div.
# 4. Once the innermost div is found:
#    a. Extract its `class` attribute.
#    b. Extract the `<a>` element’s `href` and `src` attributes.
#    c. Extract the `<time>` element’s `datetime` attribute.
# 5. **Get sibling elements** of the innermost div:

#    * Exclude the innermost div itself.
#    * Collect the **text content** from each sibling, trimming empty strings.
# 6. **Return all collected data** as an object:

#    * `topDivClass`
#    * `aHref`
#    * `aSrc`
#    * `timeDatetime`
#    * `siblingTexts` (array of strings)


# #Update: This function works.
# def get_post_title_data(driver, variable_a, timeout=5):
#     """
#     Extract data from the innermost div containing an <a> with href=variable_a and <time>.

#     Args:
#         driver: Selenium WebDriver instance.
#         variable_a: The href string to search for.

#     Returns:
#         dict with keys: topDivClass, aHref, aSrc, timeDatetime, siblingTexts
#     """
#     random_delay(2, 4.5)  # small wait to ensure content is fully loaded
#     variable_a_js = json.dumps(variable_a)  # safely quote special characters
    
#     js_code = f"""
#     function getPostTitleData(variableA) {{
#         const divs = Array.from(document.querySelectorAll('div'));
#         let innermostDiv = null;

#         for (const div of divs) {{
#             const aEl = div.querySelector(`a[href="${{variableA}}"]`);
#             const timeEl = div.querySelector('time');

#             if (aEl && timeEl) {{
#                 const childDivs = div.querySelectorAll('div');
#                 let hasNestedBoth = false;

#                 for (const child of childDivs) {{
#                     if (child.querySelector(`a[href="${{variableA}}"]`) && child.querySelector('time')) {{
#                         hasNestedBoth = true;
#                         break;
#                     }}
#                 }}

#                 if (!hasNestedBoth) {{
#                     innermostDiv = div;
#                 }}
#             }}
#         }}

#         if (!innermostDiv) return null;

#         const aEl = innermostDiv.querySelector(`a[href="${{variableA}}"]`);
#         const timeEl = innermostDiv.querySelector('time');

#         const data = {{
#             topDivClass: innermostDiv.className,
#             aHref: aEl ? aEl.getAttribute('href') : null,
#             aSrc: aEl ? aEl.getAttribute('src') : null,
#             timeDatetime: timeEl ? timeEl.getAttribute('datetime') : null,
#             siblingTexts: []
#         }};

#         const parent = innermostDiv.parentElement;
#         if (parent) {{
#             const siblings = Array.from(parent.children).filter(el => el !== innermostDiv);
#             data.siblingTexts = siblings
#                 .map(sib => sib.textContent.trim())
#                 .filter(t => t.length > 0);
#         }}

#         return data;
#     }}

#     return getPostTitleData({variable_a_js});
#     """

#     logging.info(js_code)
#     return driver.execute_script(js_code)


# def get_post_title_data_org(driver, variable_a, timeout=10):
#     """
#     Extract data from the innermost div containing an <a> with href=variable_a and <time>.
#     This version handles iframes, dynamic content, and JavaScript execution issues.

#     Args:
#         driver: Selenium WebDriver instance
#         variable_a: The href string to search for
#         timeout: Maximum time to wait for elements (default: 10 seconds)

#     Returns:
#         dict with keys: topDivClass, aHref, aSrc, timeDatetime, siblingTexts
#         or None if not found
#     """
#     original_window = driver.current_window_handle
    
#     try:
#         # Switch to default content first
#         driver.switch_to.default_content()
        
#         # Check for and handle iframes
#         iframes = driver.find_elements(By.TAG_NAME, "iframe")
#         element_found = False
        
#         # First try main document
#         try:
#             WebDriverWait(driver, 3).until(
#                 EC.presence_of_element_located((By.XPATH, f'//a[@href="{variable_a}"]'))
#             )
#             element_found = True
#             logging.info(f"Found <a> with href={variable_a} in main document")
#         except TimeoutException:
#             # If not found in main document, check iframes
#             for iframe in iframes:
#                 try:
#                     driver.switch_to.frame(iframe)
#                     WebDriverWait(driver, 3).until(
#                         EC.presence_of_element_located((By.XPATH, f'//a[@href="{variable_a}"]'))
#                     )
#                     element_found = True
#                     logging.info(f"Found <a> with href={variable_a} in iframe")
#                     break
#                 except TimeoutException:
#                     driver.switch_to.default_content()
#                     continue
            
#         if not element_found:
#             logging.warning(f"Element with href {variable_a} not found in main document or iframes")
#             return None
        
#         # Wait a bit more for dynamic content to stabilize
#         time.sleep(1)
        
#         # Prepare JavaScript code with proper error handling
#         js_code = """
#         function getPostTitleData(variableA) {
#             try {
#                 const divs = Array.from(document.querySelectorAll('div'));
#                 let innermostDiv = null;

#                 for (const div of divs) {
#                     const aEl = div.querySelector('a[href="' + variableA + '"]');
#                     const timeEl = div.querySelector('time');

#                     if (aEl && timeEl) {
#                         const childDivs = div.querySelectorAll('div');
#                         let hasNestedBoth = false;

#                         for (const child of childDivs) {
#                             if (child.querySelector('a[href="' + variableA + '"]') && child.querySelector('time')) {
#                                 hasNestedBoth = true;
#                                 break;
#                             }
#                         }

#                         if (!hasNestedBoth) {
#                             innermostDiv = div;
#                         }
#                     }
#                 }

#                 if (!innermostDiv) {
#                     console.log('No innermost div found');
#                     return null;
#                 }

#                 const aEl = innermostDiv.querySelector('a[href="' + variableA + '"]');
#                 const timeEl = innermostDiv.querySelector('time');

#                 const data = {
#                     topDivClass: innermostDiv.className,
#                     aHref: aEl ? aEl.getAttribute('href') : null,
#                     aSrc: aEl ? aEl.getAttribute('src') : null,
#                     timeDatetime: timeEl ? timeEl.getAttribute('datetime') : null,
#                     siblingTexts: []
#                 };

#                 const parent = innermostDiv.parentElement;
#                 if (parent) {
#                     const siblings = Array.from(parent.children).filter(el => el !== innermostDiv);
#                     data.siblingTexts = siblings
#                         .map(sib => sib.textContent.trim())
#                         .filter(t => t.length > 0);
#                 }

#                 return data;
#             } catch (error) {
#                 console.error('Error in getPostTitleData:', error);
#                 return null;
#             }
#         }
        
#         return getPostTitleData(arguments[0]);
#         """
        
#         # Execute JavaScript with the variable
#         result = driver.execute_script(js_code, variable_a)
        
#         if not result:
#             logging.warning("JavaScript executed but returned no results")
            
#         return result
        
#     except JavascriptException as e:
#         logging.error(f"JavaScript execution error: {e}")
#         return None
#     except Exception as e:
#         logging.error(f"Unexpected error: {e}")
#         return None
#     finally:
#         # Always return to default content and original window
#         try:
#             driver.switch_to.default_content()
#             if original_window in driver.window_handles:
#                 driver.switch_to.window(original_window)
#         except:
#             pass

# def extract_innermost_div_data_selenium(driver, variable_a, iframe_selector=None, timeout=10):
#     # Switch to iframe if needed
#     if iframe_selector:
#         WebDriverWait(driver, timeout).until(
#             EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, iframe_selector))
#         )

#     # Wait for at least one <a> with href=variable_a
#     WebDriverWait(driver, timeout).until(
#         EC.presence_of_element_located((By.CSS_SELECTOR, f'a[href="{variable_a}"]'))
#     )

#     # Find all divs
#     divs = driver.find_elements(By.TAG_NAME, 'div')
#     innermost = None

#     for div in divs:
#         try:
#             a_el = div.find_element(By.CSS_SELECTOR, f'a[href="{variable_a}"]')
#             time_el = div.find_element(By.TAG_NAME, 'time')
#         except:
#             continue  # skip divs missing <a> or <time>

#         # Check if any child div also contains both
#         child_divs = div.find_elements(By.TAG_NAME, 'div')
#         if any(
#             (child.find_elements(By.CSS_SELECTOR, f'a[href="{variable_a}"]') and
#              child.find_elements(By.TAG_NAME, 'time'))
#             for child in child_divs
#         ):
#             continue

#         innermost = div

#     if not innermost:
#         if iframe_selector:
#             driver.switch_to.default_content()
#         return None

#     # Extract data
#     a_el = innermost.find_element(By.CSS_SELECTOR, f'a[href="{variable_a}"]')
#     time_el = innermost.find_element(By.TAG_NAME, 'time')
#     parent = innermost.find_element(By.XPATH, '..')
#     siblings = [sib.text.strip() for sib in parent.find_elements(By.XPATH, '*') if sib != innermost and sib.text.strip()]

#     data = {
#         'topDivClass': innermost.get_attribute('class'),
#         'aHref': a_el.get_attribute('href'),
#         'aSrc': a_el.get_attribute('src') or None,
#         'timeDatetime': time_el.get_attribute('datetime'),
#         'siblingTexts': siblings
#     }

#     if iframe_selector:
#         driver.switch_to.default_content()

#     return data

class HumanScroller:
    def __init__(self, driver):
        self.driver = driver
        self.actions = ActionChains(driver)
        self.state = "Idle"

    def human_delay(self, base=1.0):
        return min(4.0, np.random.lognormal(mean=base, sigma=0.4))

    def next_state(self):
        transitions = {
            "Idle":   [("Burst", 0.7), ("Smooth", 0.2), ("BigJump", 0.12)], 
            "Burst":  [("Burst", 0.5), ("Smooth", 0.3), ("Idle", 0.2)],
            "Smooth": [("Smooth", 0.5), ("Burst", 0.4), ("Idle", 0.05)],
            "Jitter": [("Burst", 0.7), ("Smooth", 0.2), ("Idle", 0.09)],
            "BigJump":[("Burst", 0.5), ("Smooth", 0.4), ("Idle", 0.1)],
        }
        choices, probs = zip(*transitions[self.state])
        self.state = random.choices(choices, probs)[0]

    def perform(self, steps=30):
        for _ in range(steps):
            if self.state == "Idle":
                time.sleep(self.human_delay(base=1.0))

            elif self.state == "Burst":
                for _ in range(random.randint(2, 4)):
                    dy = random.randint(120, 280)
                    if random.random() < 0.1:  # small chance scroll up
                        dy = -dy
                    self.actions.scroll_by_amount(0, dy).perform()
                    time.sleep(self.human_delay(base=0.1))

            elif self.state == "Smooth":
                dy = random.randint(200, 400)
                self.actions.scroll_by_amount(0, dy).perform()
                time.sleep(self.human_delay(base=0.5))

            elif self.state == "Jitter":
                dy = random.choice([-80, -40, 40, 80])
                self.actions.scroll_by_amount(0, dy).perform()
                time.sleep(self.human_delay(base=0.2))

            elif self.state == "BigJump":
                if random.random() < 0.5:
                    self.actions.send_keys(Keys.PAGE_DOWN).perform()
                else:
                    self.actions.send_keys(Keys.SPACE).perform()
                time.sleep(self.human_delay(base=1.5))

            self.next_state()

def scroll_with_mouse(
    self,
    steps: int = 10,
    min_step: int = 150,
    max_step: int = 400,
    min_delay: float = 0.2,
    max_delay: float = 0.6
):
    """
    Scrolls the main page down in a human-like manner using the mouse wheel.
    """
    actions = ActionChains(self.driver)

    for i in range(steps):
        # direction (mostly down, sometimes up)
        direction = 1 if random.random() > 0.1 else -1
        
        # inertia-like scroll size
        factor = (1 - abs((i - steps/2) / (steps/2)))  # bell-shaped
        base_step = random.triangular(min_step, max_step, (min_step+max_step)//2)
        delta_y = int(direction * base_step * (0.5 + factor))
        
        # occasional jitter
        if random.random() < 0.05:
            delta_y = random.choice([-50, 50])
        
        actions.scroll_by_amount(0, delta_y).perform()
        
        # clustered bursts + pauses
        if random.random() < 0.2:
            time.sleep(random.uniform(1.5, 4.0))  # reading pause
        else:
            time.sleep(random.uniform(min_delay, max_delay))

def save_intermediate(post_data, tmp_file):
    """
    Appends a single post's data to a temporary JSONL file.

    This is used for crash recovery, ensuring that scraped data is not lost if the
    script fails before a full batch is saved.

    Args:
        post_data: A dictionary containing the data for a single post.
        tmp_file: The path to the temporary file.
    """
    # Ensure the parent directory exists before writing.
    Path(tmp_file).parent.mkdir(parents=True, exist_ok=True)
    with open(tmp_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(post_data, ensure_ascii=False) + "\n")

def clear_tmp_file(tmp_file):
    """Clears the temporary file by opening it in write mode."""
    try:
        open(tmp_file, "w").close()
    except Exception as e:
        logger.warning(f"Failed to clear tmp file {tmp_file}: {e}")



# def scrape_posts_in_batches(
#     backend,
#     post_elements,
#     config,
#     batch_size=3,
#     save_every=5,
#     output_dir=".",
#     tab_open_retries=4,
#     debug=False
# ):
#     """
#     Robust batch scraper that opens posts in new tabs, scrapes them, closes each tab,
#     and saves results periodically.

#     Important behaviors/fixes:
#     - DOES NOT call `window.location.href` (that navigates the current tab)
#     - Waits for new window handle reliably (with small retries)
#     - Always closes the scraped tab in a finally block and switches back to main handle
#     - Uses WebDriverWait for elements where appropriate (backend.extract_comments etc still
#       govern their own waits)
#     - Optional debug flag to keep tabs open / print extra info
#     """
#     results = {"scraped_posts": [], "skipped_posts": []}
#     total_scraped = 0

#     driver = backend.driver
#     main_handle = driver.current_window_handle
#     tmp_file = os.path.join(output_dir, f"scrape_results_tmp_{config.target_profile}.jsonl")

#     # helper: open href in new tab and return new handle (or raise)
#     def open_href_in_new_tab(href):
#         before_handles = set(driver.window_handles)
#         # Open new tab with specified href - this opens a new tab in most browsers
#         driver.execute_script("window.open(arguments[0], '_blank');", href)

#         # Wait for the new handle to appear
#         new_handle = None
#         for attempt in range(tab_open_retries):
#             after_handles = set(driver.window_handles)
#             diff = after_handles - before_handles
#             if diff:
#                 new_handle = diff.pop()
#                 break
#             time.sleep(0.5 + random.random() * 0.5)  # jittered wait
#         if not new_handle:
#             raise RuntimeError(f"New tab did not appear for href={href}")
#         return new_handle

#     # main loop over batches
#     for batch_start in range(0, len(post_elements), batch_size):
#         batch = post_elements[batch_start: batch_start + batch_size]
#         opened = []  # list of tuples (index, href, handle)

#         # --- open all posts in batch (in new tabs) ---
#         for i, post_element in enumerate(batch, start=batch_start):
#             # if i == 0:
#                 # continue
#             try:
#                 # href = post_element.get_attribute("href")
#                 href = post_element
#                 if not href:
#                     logger.warning(
#                         f"Skipping post {i+1} from profile {config.target_profile}: missing href."
#                     )
#                     results["skipped_posts"].append({
#                         "index": i,
#                         "reason": "missing href",
#                         "profile": config.target_profile
#                     })
#                     continue

#                 try:
#                     new_handle = open_href_in_new_tab(href)
#                     # optionally give the new tab a moment to start loading
#                     time.sleep(random.uniform(0.8, 1.5))
#                     opened.append((i, href, new_handle))
#                     logger.info(f"Opened post {i+1} in new tab: {href} -> handle {new_handle}")
#                 except Exception as e:
#                     logger.error(f"Failed to open new tab for post {i+1}: {e}")
#                     results["skipped_posts"].append({
#                         "index": i,
#                         "reason": f"failed to open tab: {str(e)}",
#                         "profile": config.target_profile
#                     })
#             except Exception as e:
#                 logger.exception(f"Unexpected error when preparing post {i+1}: {e}")
#                 results["skipped_posts"].append({
#                     "index": i,
#                     "reason": f"error extracting href: {str(e)}",
#                     "profile": config.target_profile
#                 })

#         # --- scrape each opened tab, one-by-one, ensuring closure ---
#         for i, href, handle in opened:
#             try:
#                 # switch to the new tab
#                 driver.switch_to.window(handle)
#                 human_mouse_move(driver,duration=random.randrange(1, 2))
#                 logger.info(f"Switched to tab {handle} for post {i} ({href})")
#                 # optional short wait for page to start loading
#                 try:
#                     # If you have a reliable "post content" element to wait for, use it here.
#                     # Example (commented): WebDriverWait(driver, page_load_timeout).until(
#                     #     EC.presence_of_element_located((By.CSS_SELECTOR, "article"))
#                     # )
#                     time.sleep(random.uniform(0.6, 1.2))
#                 except Exception:
#                     # non-fatal - proceed and rely on backend.extract_* waits
#                     logger.debug("Page load wait did not find expected element, continuing.")

#                 post_id = f"post_{i}"
#                 post_data = {
#                     "post_url": href,
#                     "post_id": post_id,
#                     "post_title": None,
#                     "post_images": [],
#                     "post_comments": [],
#                 }

#                 # # Comments
#                 # try:
#                 #     post_data["post_comments"] = backend.extract_comments(steps=80) or []
#                 # except Exception as e:
#                 #     logger.error(f"Comments extraction failed for {href}: {e}")
#                 #     logger.debug(traceback.format_exc())
#                 # Title / metadata
#                 try:
#                     handle_slug = f"/{config.target_profile}/"
#                     logger.info(f"Extracting title data for {href} with handle {handle_slug}")
#                     post_data["post_title"] = get_post_title_data(driver, handle_slug) or ""
#                 except Exception as e:
#                     logger.error(f"Title extraction failed for {href}: {e}")
#                     logger.debug(traceback.format_exc())

#                 # Images
#                 try:
#                     post_data["post_images"] = images_from_post(driver) or []
#                     logger.info(f"Images extraction successful for {href}")
#                     logger.info(f'{post_data["post_images"]}')
#                 except Exception as e:
#                     logger.error(f"Images extraction failed for {href}: {e}")
#                     logger.debug(traceback.format_exc())

#                 # Likes / other sections
#                 try:
#                     post_data["likes"] = get_section_with_highest_likes(driver) or {}
#                     logger.info(f"Likes extraction successful for {href}")
#                 except Exception as e:
#                     logger.error(f"Likes extraction failed for {href}: {e}")
#                     logger.debug(traceback.format_exc())
                
#                 # comments
#                 try:
#                     post_data["post_comments_gif"] = scrape_comments_with_gif(backend.driver) or []
#                 except Exception as e:
#                     logger.error(f"Comments extraction with gif failed for {href}: {e}")
#                     logger.debug(traceback.format_exc())


#                 results["scraped_posts"].append(post_data)
#                 total_scraped += 1
#                 logger.info(f"Scraped post {i} ({href}). Total scraped: {total_scraped}")

#                 # --- save every result immediately to tmp file ---
#                 try:
#                     save_intermediate(post_data, tmp_file)
#                 except Exception as e:
#                     logger.warning(f"Failed to write tmp result for {href}: {e}")

#                 # --- every N posts, save final and clear tmp ---
#                 if total_scraped % save_every == 0:
#                     save_scrape_results(results, output_dir,config)
#                     clear_tmp_file(tmp_file)
#                     logger.info(f"Saved results after {total_scraped} scraped posts.")


#             except Exception as e:
#                 logger.exception(f"Unexpected error while scraping post {i} ({href}): {e}")
#                 results["skipped_posts"].append({
#                     "index": i,
#                     "reason": str(e),
#                     "profile": config.target_profile
#                 })
#             finally:
#                 # Ensure this tab is closed and we switch back to a known handle.
#                 try:
#                     if debug:
#                         logger.info(f"DEBUG mode: leaving tab {handle} open.")
#                     else:
#                         driver.close()
#                         logger.debug(f"Closed tab {handle}")
#                 except Exception as e:
#                     logger.warning(f"Error closing tab {handle}: {e}")
#                 # switch back to main handle (if it's still present) or to any remaining handle
#                 handles = driver.window_handles
#                 if not handles:
#                     logger.info("No browser windows left after closing tab.")
#                     return results
#                 # prefer main_handle if still available
#                 if main_handle in handles:
#                     driver.switch_to.window(main_handle)
#                 else:
#                     # fallback to last handle
#                     driver.switch_to.window(handles[0])
#                 logger.debug(f"Switched back to handle {driver.current_window_handle}")

#         # optional: jittered wait between batches to mimic human rate-limits
#         random_delay(config.rate_limit_seconds_min, config.rate_limit_seconds_max)

#     # final save
#     if results["scraped_posts"] or results["skipped_posts"]:
#         save_scrape_results(results, output_dir, config)
#         clear_tmp_file(tmp_file)
#         logger.info("Saved final scrape results.")

#     return results


def save_scrape_results(results: dict, output_dir: str, config: dict):
    """
    Saves the collected scraped and skipped posts to their final destination files.

    After writing the data, it clears the in-memory lists to free up memory.

    Args:
        results: A dictionary containing 'scraped_posts' and 'skipped_posts' lists.
        output_dir: The base directory for output files (used for mkdir).
        config: The application's configuration object, used to get file paths.
    """
    metadata_file = config.data.metadata_path
    skipped_file = config.data.skipped_path

    # Save scraped posts
    if results.get("scraped_posts"):
        # Ensure the parent directory exists before writing.
        Path(metadata_file).parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_file, "a", encoding="utf-8") as f:
            for post in results["scraped_posts"]:
                f.write(json.dumps(post, ensure_ascii=False) + "\n")

    # Save skipped posts
    if results.get("skipped_posts"):
        # Ensure the parent directory exists before writing.
        Path(skipped_file).parent.mkdir(parents=True, exist_ok=True)
        with open(skipped_file, "a", encoding="utf-8") as f:
            for post in results["skipped_posts"]:
                f.write(json.dumps(post, ensure_ascii=False) + "\n")
    # Clear results list after saving
    results["scraped_posts"].clear()
    results["skipped_posts"].clear()

import time
import random
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

import time
import random
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By

# def human_scroll_and_scrape_comments(driver,
#                                      top_div_selector=None,
#                                      scroll_steps=4,
#                                      min_step_px=100,
#                                      max_step_px=350,
#                                      micro_pause=(0.25, 0.8),
#                                      read_pause=(1.0, 2.2),
#                                      max_scrolls=20,
#                                      wait_timeout=10):
#     """
#     Find the real comments scroll container via JS, scroll it in a human-like way,
#     and return parsed comments.

#     Parameters
#     ----------
#     driver : selenium.webdriver
#         Active webdriver instance, page already loaded to comments.
#     top_div_selector : str or None
#         Optional CSS selector for the "topDiv" comment blocks. If None, function
#         will search all <div>s using the structural heuristic (div > div > div).
#     scroll_steps : int
#         Number of micro scroll steps to perform per scroll iteration (human-like).
#     min_step_px, max_step_px : int
#         Pixel range for each micro-step.
#     micro_pause : tuple(float,float)
#         Pause (seconds) between micro-steps (random between these).
#     read_pause : tuple(float,float)
#         Pause (seconds) after a group of micro-steps to simulate reading.
#     max_scrolls : int
#         Max iterations of the (micro-steps + read pause) loop.
#     wait_timeout : int/float
#         Seconds to try to find a suitable comment container before raising TimeoutException.

#     Returns
#     -------
#     list of dict
#         Each dict has keys 'handle','date','comment','likes' (as returned by the parser JS).
#     """
#     # JS to find best scrollable ancestor and also return a short selector (returns [el, selector] or null)
#     js_find_container = r"""
#     (function(sel){
#         function isScrollableStyle(el){
#             if(!el) return false;
#             const s = window.getComputedStyle(el);
#             const oy = s.overflowY || s.overflow || '';
#             return /auto|scroll|overlay/i.test(oy) && el.scrollHeight > el.clientHeight;
#         }
#         function hasOverflowPotential(el){
#             if(!el) return false;
#             const s = window.getComputedStyle(el);
#             const oy = s.overflowY || s.overflow || '';
#             return /auto|scroll|overlay|hidden/i.test(oy);
#         }
#         function cssPath(el){
#             if(!el) return null;
#             if(el.id) return '#' + el.id;
#             const parts = [];
#             let cur = el;
#             while(cur && cur.nodeType === 1 && cur.tagName.toLowerCase() !== 'html') {
#                 let part = cur.tagName.toLowerCase();
#                 if(cur.className){
#                     const cls = String(cur.className).split(/\s+/).filter(Boolean)[0];
#                     if(cls) part += '.' + cls.replace(/[^a-zA-Z0-9_-]/g,'');
#                 } else {
#                     const parent = cur.parentElement;
#                     if(parent){
#                         const idx = Array.from(parent.children).indexOf(cur) + 1;
#                         part += ':nth-child(' + idx + ')';
#                     }
#                 }
#                 parts.unshift(part);
#                 cur = cur.parentElement;
#                 if(parts.length > 6) break;
#             }
#             return parts.length ? parts.join(' > ') : el.tagName.toLowerCase();
#         }

#         const selector = sel || null;
#         const allDivs = selector ? Array.from(document.querySelectorAll(selector)) : Array.from(document.querySelectorAll('div'));
#         const topDivs = allDivs.filter(topDiv => {
#             try {
#                 const profileDiv = topDiv.querySelector('div > div > div');
#                 const candidates = Array.from(topDiv.querySelectorAll('div > div > div'));
#                 const commentDiv = candidates.find(div => !div.querySelector('span a, span time'));
#                 return !!profileDiv && !!commentDiv;
#             } catch(e){
#                 return false;
#             }
#         });

#         if(topDivs.length === 0) return null;

#         const map = new Map();
#         topDivs.forEach(td => {
#             let el = td;
#             const visited = new Set();
#             while(el && el !== document.documentElement && !visited.has(el)){
#                 visited.add(el);
#                 if(el.nodeType === 1){
#                     const entry = map.get(el) || {count: 0, scrollable: false, overflowPotential: false};
#                     entry.count += 1;
#                     if(isScrollableStyle(el)) entry.scrollable = true;
#                     if(hasOverflowPotential(el)) entry.overflowPotential = true;
#                     map.set(el, entry);
#                 }
#                 el = el.parentElement;
#             }
#         });

#         const candidates = Array.from(map.entries()).map(([el, meta]) => {
#             return {el: el, count: meta.count, scrollable: meta.scrollable, overflowPotential: meta.overflowPotential,
#                     gap: (el.scrollHeight - el.clientHeight)};
#         });

#         if(candidates.length === 0) return null;

#         candidates.sort((a,b) => {
#             if(a.scrollable !== b.scrollable) return a.scrollable ? -1 : 1;
#             if(a.count !== b.count) return b.count - a.count;
#             if(a.overflowPotential !== b.overflowPotential) return a.overflowPotential ? -1 : 1;
#             return b.gap - a.gap;
#         });

#         let best = candidates.find(c => c.count >= 3) || candidates[0];
#         if(best.gap <= 0){
#             const positive = candidates.find(c => c.gap > 0 && (c.scrollable || c.overflowPotential));
#             if(positive) best = positive;
#         }

#         // return the element and a short selector for later use
#         return [best.el, cssPath(best.el)];
#     })(arguments[0]);
#     """
#     # pdb.set_trace()
#     # small helper to repeatedly try to find a container until wait_timeout
#     end_time = time.time() + wait_timeout
#     container_info = None
#     while time.time() < end_time:
#         try:
#             container_info = driver.execute_script(js_find_container, top_div_selector)
#         except Exception:
#             container_info = None
#         if container_info:
#             break
#         time.sleep(0.2)
#     if not container_info:
#         raise TimeoutException("Couldn't find comments topDiv/container within timeout. Try supplying top_div_selector.")

#     # container_info expected [WebElement, selector_string]
#     container_el = container_info[0]  # Selenium WebElement
#     chosen_selector = container_info[1] if len(container_info) > 1 else None

#     # Fallback: if container_el is falsy, use document.scrollingElement
#     if container_el is None:
#         container_el = driver.execute_script("return document.scrollingElement || document.documentElement || document.body;")

#     # scrolling loop (human-like)
#     last_height = -1
#     for _ in range(max_scrolls):
#         # do 'scroll_steps' micro-step scrolls
#         for _step in range(max(1, int(scroll_steps))):
#             step_px = random.randint(int(min_step_px), int(max_step_px))
#             try:
#                 driver.execute_script("arguments[0].scrollTop += arguments[1];", container_el, step_px)
#             except StaleElementReferenceException:
#                 # re-find container and retry once
#                 container_info = driver.execute_script(js_find_container, top_div_selector) or driver.execute_script("return document.scrollingElement || document.documentElement || document.body;")
#                 container_el = container_info[0] if isinstance(container_info, (list,tuple)) and container_info[0] else container_info
#                 driver.execute_script("arguments[0].scrollTop += arguments[1];", container_el, step_px)
#             time.sleep(random.uniform(float(micro_pause[0]), float(micro_pause[1])))

#         # reading pause
#         time.sleep(random.uniform(float(read_pause[0]), float(read_pause[1])))

#         # check whether new content loaded
#         try:
#             new_height = driver.execute_script("return arguments[0].scrollHeight;", container_el)
#         except StaleElementReferenceException:
#             container_info = driver.execute_script(js_find_container, top_div_selector) or driver.execute_script("return document.scrollingElement || document.documentElement || document.body;")
#             container_el = container_info[0] if isinstance(container_info, (list,tuple)) and container_info[0] else container_info
#             new_height = driver.execute_script("return arguments[0].scrollHeight;", container_el)

#         if new_height == last_height:
#             break
#         last_height = new_height

#     # Parse comments using your parser JS and return to Python
#     js_parse = r"""
#     (function parseComments(){
#         const results = [];
#         const seen = new Set();
#         // Heuristic parser (adjust selectors inside if needed)
#         const topDivs = Array.from(document.querySelectorAll('div')).filter(topDiv => {
#             try {
#                 const profileDiv = topDiv.querySelector('div > div > div');
#                 const candidates = Array.from(topDiv.querySelectorAll('div > div > div'));
#                 const commentDiv = candidates.find(div => !div.querySelector('span a, span time'));
#                 return !!profileDiv && !!commentDiv;
#             } catch(e){
#                 return false;
#             }
#         });

#         topDivs.forEach(topDiv => {
#             const profileDiv = topDiv.querySelector('div > div > div');
#             const commentDiv = Array.from(topDiv.querySelectorAll('div > div > div'))
#                 .find(div => !div.querySelector('span a, span time'));
#             if (!profileDiv || !commentDiv) return;

#             const data = { likes: null, handle: null, date: null, comment: null };

#             const likeSpan = Array.from(topDiv.querySelectorAll('span'))
#                 .map(s => s.innerText && s.innerText.trim())
#                 .filter(Boolean)
#                 .find(t => /\b\d{1,3}(?:,\d{3})*(?:\.\d+)?[kKmM]?\s+likes?\b/i.test(t));
#             if (likeSpan) data.likes = likeSpan;

#             const spans = profileDiv.querySelectorAll('span');
#             spans.forEach(span => {
#                 const aTag = span.querySelector('a');
#                 if (aTag && !data.handle) data.handle = aTag.innerText.trim();
#                 const timeTag = span.querySelector('time');
#                 if (timeTag && !data.date) data.date = timeTag.innerText.trim();
#             });

#             const text = commentDiv.innerText.trim();
#             if (text) data.comment = text;

#             if (data.comment && data.date) {
#                 const key = (data.handle || '') + '::' + data.comment;
#                 if (!seen.has(key)) {
#                     seen.add(key);
#                     results.push(data);
#                 }
#             }
#         });

#         return results;
#     })();
#     """
#     comments = driver.execute_script(js_parse)
#     return comments


from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time

def find_comment_container(driver, min_matches=3):
    """
    Executes a JavaScript heuristic to find the best scrollable container for comments.

    The script works by:
    1. Identifying potential "comment block" divs based on their structure.
    2. Walking up the DOM from each comment block, counting how many blocks share a common ancestor.
    3. Scoring ancestors based on the number of comment blocks they contain and whether they are scrollable.
    4. Highlighting the top candidates in the browser for debugging and returning the best one.

    Args:
        driver: The Selenium WebDriver instance.
        min_matches: The minimum number of comment blocks an ancestor must contain to be a strong candidate.
    """
    js_code = """
        return (function(minMatches){
            const logs = [];

            function log(...args){
                logs.push(args.join(" "));
            }

            function isScrollableStyle(el){
                if(!el) return false;
                const s = window.getComputedStyle(el);
                const oy = s.overflowY || s.overflow || '';
                return /auto|scroll|overlay/i.test(oy) && el.scrollHeight > el.clientHeight;
            }
            function hasOverflowPotential(el){
                if(!el) return false;
                const s = window.getComputedStyle(el);
                const oy = s.overflowY || s.overflow || '';
                return /auto|scroll|overlay|hidden/i.test(oy);
            }
            function info(el){
                if(!el) return null;
                log("→ Candidate element:", el.tagName, "class:", el.className || "(no class)");
                log("   scrollHeight:", el.scrollHeight, "clientHeight:", el.clientHeight);
                log("   overflow-y:", window.getComputedStyle(el).overflowY);
                return el;
            }
            function cssPath(el){
                if(!el) return null;
                if(el.id) return `#${el.id}`;
                const parts = [];
                let cur = el;
                while(cur && cur.nodeType === 1 && cur.tagName.toLowerCase() !== 'html'){
                    let part = cur.tagName.toLowerCase();
                    if(cur.className){
                        const cls = String(cur.className).split(/\\s+/).filter(Boolean)[0];
                        if(cls) part += `.${cls.replace(/[^a-zA-Z0-9_-]/g,'')}`;
                    } else {
                        const parent = cur.parentElement;
                        if(parent){
                            const idx = Array.from(parent.children).indexOf(cur) + 1;
                            part += `:nth-child(${idx})`;
                        }
                    }
                    parts.unshift(part);
                    cur = cur.parentElement;
                    if(parts.length > 6) break;
                }
                return parts.length ? parts.join(' > ') : el.tagName.toLowerCase();
            }

            log("🚀 Starting container detection with minMatches =", minMatches);

            const allDivs = Array.from(document.querySelectorAll('div'));
            const topDivs = allDivs.filter(topDiv => {
                try {
                    const profileDiv = topDiv.querySelector('div > div > div');
                    const candidates = Array.from(topDiv.querySelectorAll('div > div > div'));
                    const commentDiv = candidates.find(div => !div.querySelector('span a, span time'));
                    return !!profileDiv && !!commentDiv;
                } catch(e){
                    return false;
                }
            });

            if(topDivs.length === 0){
                log("⚠️ No matching comment topDivs found.");
                return {logs};
            }
            log("✅ Found", topDivs.length, "candidate comment topDivs.");

            const map = new Map();
            topDivs.forEach(td => {
                let el = td;
                const visited = new Set();
                while(el && el !== document.documentElement && !visited.has(el)){
                    visited.add(el);
                    if(el.nodeType === 1){
                        const entry = map.get(el) || {count: 0, scrollable: false, overflowPotential: false};
                        entry.count += 1;
                        if(isScrollableStyle(el)) entry.scrollable = true;
                        if(hasOverflowPotential(el)) entry.overflowPotential = true;
                        map.set(el, entry);
                    }
                    el = el.parentElement;
                }
            });

            const candidates = Array.from(map.entries()).map(([el, meta]) => {
                return {el, count: meta.count, scrollable: meta.scrollable, overflowPotential: meta.overflowPotential,
                        gap: (el.scrollHeight - el.clientHeight)};
            });

            if(candidates.length === 0){
                log("⚠️ No ancestor candidates collected.");
                return {logs};
            }

            candidates.sort((a,b) => {
                if(a.scrollable !== b.scrollable) return a.scrollable ? -1 : 1;
                if(a.count !== b.count) return b.count - a.count;
                if(a.overflowPotential !== b.overflowPotential) return a.overflowPotential ? -1 : 1;
                return b.gap - a.gap;
            });

            let best = candidates.find(c => c.count >= minMatches) || candidates[0];
            if(best.gap <= 0){
                const positive = candidates.find(c => c.gap > 0 && (c.scrollable || c.overflowPotential));
                if(positive) best = positive;
            }

            candidates.slice(0,3).forEach((c, idx) => {
                try {
                    c.el.style.outline = (idx===0) ? '3px solid red' : (idx===1) ? '3px dashed orange' : '2px dashed yellow';
                } catch(e){}
                log(`#${idx+1} candidate: count=${c.count}, scrollable=${c.scrollable}, gap=${c.gap}`);
                info(c.el);
            });

            const selector = cssPath(best.el);
            log("🎯 SELECTOR for chosen container:", selector);

            return {selector, logs};
        })(arguments[0]);
    """

    return driver.execute_script(js_code, min_matches)


import random
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

# def human_scroll_bk(driver, selector, steps=10, min_step=100, max_step=400, min_pause=0.3, max_pause=1.2):
#     """
#     Scroll inside the element identified by `selector` in a human-like way.
    
#     Args:
#         driver: Selenium WebDriver instance
#         selector: CSS selector string for the scrollable container
#         steps: number of scroll increments
#         min_step: minimum scroll step in pixels
#         max_step: maximum scroll step in pixels
#         min_pause: minimum pause between steps (seconds)
#         max_pause: maximum pause between steps (seconds)
#     """
#     el = driver.find_element(By.CSS_SELECTOR, selector)
#     actions = ActionChains(driver)
    
#     for i in range(steps):
#         # Random scroll amount
#         scroll_by = random.randint(min_step, max_step)
#         if random.choice([True, False]):
#             human_mouse_move(driver, selector=selector,duration=random.randrange(1, 3))
#         # Execute JS to scroll the element
#         driver.execute_script("arguments[0].scrollBy(0, arguments[1]);", el, scroll_by)
        
#         # Optional: small mouse movement over the container (looks more human)
#         actions.move_to_element_with_offset(el, random.randint(10, 50), random.randint(10, 50)).perform()
        
#         # Random pause
#         pause = round(random.uniform(min_pause, max_pause), 2)
#         print(f"Step {i+1}/{steps}: scrolled by {scroll_by}px, sleeping {pause}s")
#         time.sleep(pause)
# import random
# import time
# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.action_chains import ActionChains

def human_scroll(
    driver,
    selector,
    steps=10,
    min_step=180,
    max_step=400,
    min_pause=0.3,
    max_pause=1.1,
    max_retries=8,  # max consecutive retries with no height change
):
    """
    Scrolls inside a specific element in a human-like way, with stop conditions.

    This function simulates a user scrolling through a container. It stops scrolling
    if it detects that it has reached the bottom or if multiple scroll attempts
    fail to load new content (i.e., the scroll height does not change).

    Args:
        driver: The Selenium WebDriver instance.
        selector: The CSS selector for the scrollable container.
        steps: The maximum number of scroll increments to perform.
        max_retries: The number of times to retry scrolling if no new content is loaded.
    """
    el = driver.find_element(By.CSS_SELECTOR, selector)
    actions = ActionChains(driver)

    last_scroll_top = driver.execute_script("return arguments[0].scrollTop;", el)
    max_scroll_height = driver.execute_script("return arguments[0].scrollHeight;", el)

    retry_count = 0
    wait_retry_count = 0
    for i in range(steps):
        client_height = driver.execute_script("return arguments[0].clientHeight;", el)

        # Stop if at bottom
        if last_scroll_top + client_height >= max_scroll_height:
            print(f"Probably reached bottom at step {i+1}. retry count {wait_retry_count}")
            wait_retry_count += 1
            if wait_retry_count >= 3:
                print(f"Waiting too long at step {i+1}, giving up.")
                break
            random_delay(1, 3)
        wait_retry_count = 0
        # Random scroll amount
        scroll_by = random.randint(min_step, max_step)

        if random.choice([True, False, False, False]):
            human_mouse_move(driver, selector=selector, duration=random.randrange(1, 3))

        driver.execute_script("arguments[0].scrollBy(0, arguments[1]);", el, scroll_by)

        new_scroll_top = driver.execute_script("return arguments[0].scrollTop;", el)
        new_scroll_height = driver.execute_script("return arguments[0].scrollHeight;", el)

        if new_scroll_top == last_scroll_top and new_scroll_height == max_scroll_height:
            retry_count += 1
            random_delay(1, 4)
            print(f"No height change detected at step {i+1}, retry {retry_count}/{max_retries}")
            if retry_count >= max_retries:
                print(f"Max retries reached at step {i+1}, exiting scroll.")
                break
        else:
            retry_count = 0  # reset retries if height changed

        last_scroll_top = new_scroll_top
        max_scroll_height = new_scroll_height

        # Optional small mouse movement
        actions.move_to_element_with_offset(el, random.randint(10, 50), random.randint(10, 50)).perform()

        # Random pause
        pause = round(random.uniform(min_pause, max_pause), 2)
        print(f"Step {i+1}/{steps}: scrolled by {scroll_by}px, sleeping {pause}s")
        time.sleep(pause)

def robust_mouse_move(driver, element, duration=1.5, steps=12):
    actions = ActionChains(driver)
    result = {"points": [], "success": False}

    try:
        rect = driver.execute_script(
            "const r=arguments[0].getBoundingClientRect();"
            "return {left:r.left, top:r.top, width:r.width, height:r.height};",
            element,
        )

        left, top, width, height = rect["left"], rect["top"], rect["width"], rect["height"]
        start_x, start_y = left + width/2, top + height/2

        # Generate target points
        points = [(start_x, start_y)]
        for _ in range(steps-1):
            x = random.uniform(left+5, left+width-5)
            y = random.uniform(top+5, top+height-5)
            points.append((x,y))

        # --- distribute duration into (steps-1) intervals ---
        # random positive weights
        weights = np.random.lognormal(mean=0, sigma=0.6, size=len(points)-1)
        weights = weights / weights.sum()
        intervals = weights * duration   # guaranteed sum = duration

        # Perform moves
        for (x,y), interval in zip(points[1:], intervals):
            try:
                actions.move_to_element_with_offset(element, int(x-left), int(y-top)).perform()
            except:
                driver.execute_script(
                    "const ev=new MouseEvent('mousemove',{bubbles:true,clientX:arguments[0],clientY:arguments[1]});"
                    "document.elementFromPoint(arguments[0],arguments[1])?.dispatchEvent(ev);",
                    int(x), int(y))
            result["points"].append((int(x), int(y), interval))
            time.sleep(interval)
        
        result["success"] = True
        return result
    except Exception as e:
        result["error"] = str(e)
        return result


def human_mouse_move(
    driver: WebDriver,
    element: Optional[WebElement] = None,
    selector: Optional[str] = None,
    duration: float = 1.2,
    steps: int = 12,
    margin: int = 6,
    pause_jitter: Tuple[float, float] = (0.02, 0.12),
    use_action_chains: bool = True,
    seed: Optional[int] = None,
) -> Dict:
    """
    Moves the mouse in a human-like, randomized path over a given element.

    This function simulates realistic mouse movement by generating a series of
    intermediate points and moving the mouse between them with small, randomized
    pauses. It can use either Selenium's ActionChains or direct JavaScript
    mouse events.

    Args:
        driver: The Selenium WebDriver instance.
        element: The target WebElement to move the mouse over.
        selector: A CSS selector to find the element if `element` is not provided.
        duration: The approximate total time (in seconds) for the movement.
        steps: The number of intermediate points in the path (more steps = smoother).
        use_action_chains: If True, use ActionChains. If False, use JavaScript events.

    Returns:
        A dictionary containing the success status, a list of points visited, and any error.
    Notes:
        - In headless mode, visible movement may not be meaningful, but events still fire.
        - ActionChains offsets are computed relative to element's top-left.
    """
    if seed is not None:
        random.seed(seed)

    result = {"success": False, "points": [], "error": None}

    try:
        # Resolve element
        if element is None and selector:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
            except Exception as e:
                result["error"] = f"selector not found: {e}"
                return result

        # Get bounding rect (client coordinates)
        if element is not None:
            rect = driver.execute_script(
                "const r = arguments[0].getBoundingClientRect();"
                "return {left: r.left, top: r.top, width: r.width, height: r.height};",
                element,
            )
        else:
            # Use viewport (body) if no element
            vp = driver.execute_script(
                "return {left: 0, top: 0, width: Math.max(document.documentElement.clientWidth, window.innerWidth || 0),"
                "height: Math.max(document.documentElement.clientHeight, window.innerHeight || 0)};"
            )
            rect = vp

        # Sanity clamp
        width = max(1, int(rect.get("width", 1)))
        height = max(1, int(rect.get("height", 1)))
        left = float(rect.get("left", 0))
        top = float(rect.get("top", 0))

        # Ensure margin leaves room
        margin = max(0, min(margin, min(width // 3, height // 3)))

        # Starting point: center of element
        start_x = left + width / 2.0
        start_y = top + height / 2.0

        # Build a sequence of target points using smooth-ish random walk toward random edges/points
        points: List[Tuple[float, float]] = []
        for i in range(steps):
            # target region bias: sometimes nearer edges, sometimes center
            t = i / max(1, steps - 1)
            # sample within inner box
            x = random.uniform(left + margin, left + width - margin)
            y = random.uniform(top + margin, top + height - margin)

            # small lerp from previous toward new random target to smooth jumps
            if points:
                prev_x, prev_y = points[-1]
                # move fractionally toward new random target
                frac = random.uniform(0.2, 0.8)
                x = prev_x + (x - prev_x) * frac
                y = prev_y + (y - prev_y) * frac
            else:
                # first step should be close to center
                x = start_x + (x - start_x) * random.uniform(0.15, 0.6)
                y = start_y + (y - start_y) * random.uniform(0.15, 0.6)

            # clamp to element bounds
            x = max(left + 1, min(left + width - 1, x))
            y = max(top + 1, min(top + height - 1, y))
            points.append((x, y))

        # Add final subtle pause and maybe small corrective movement back toward center
        if random.random() < 0.4:
            points.append((start_x + random.uniform(-5, 5), start_y + random.uniform(-5, 5)))

        # Map points to timestamps distributed across duration
        now = time.time()
        timestamps = []
        for idx in range(len(points)):
            # distribute nonlinearly: small random jitter around equal spacing
            frac = (idx / max(1, len(points) - 1))
            ts = now + frac * duration + random.uniform(-0.02, 0.05)
            timestamps.append(ts)

        # Perform movements
        if use_action_chains:
            actions = ActionChains(driver)
            # Move to first point by moving to element and offset
            for (x, y), ts in zip(points, timestamps):
                # offsets relative to element top-left
                offset_x = int(round(x - left))
                offset_y = int(round(y - top))

                # clamp offsets to element sizes (ActionChains expects offsets inside element)
                offset_x = max(0, min(width - 1, offset_x))
                offset_y = max(0, min(height - 1, offset_y))

                try:
                    actions.move_to_element_with_offset(element if element is not None else driver.find_element(By.TAG_NAME, "body"), offset_x, offset_y)
                    actions.perform()
                except WebDriverException:
                    # fallback: attempt a JS dispatch if ActionChains fails mid-run
                    driver.execute_script(
                        """
                        (function(cx, cy){
                          const ev = new MouseEvent('mousemove', {bubbles:true, cancelable:true, clientX:cx, clientY:cy});
                          document.elementFromPoint(cx, cy)?.dispatchEvent(ev);
                        })(arguments[0], arguments[1]);
                        """,
                        int(round(x)), int(round(y))
                    )

                # sleep a bit (distributed)
                pause = random.uniform(pause_jitter[0], pause_jitter[1])
                time.sleep(pause)
                result["points"].append((int(round(x)), int(round(y)), time.time()))
        else:
            # Use JS synthetic MouseEvents (fires events on the element at client coordinates)
            dispatch_script = """
                (function(cx, cy){
                  const targ = document.elementFromPoint(cx, cy) || document.body;
                  const evMove = new MouseEvent('mousemove', {bubbles:true, cancelable:true, clientX:cx, clientY:cy});
                  const evOver = new MouseEvent('mouseover', {bubbles:true, cancelable:true, clientX:cx, clientY:cy});
                  targ.dispatchEvent(evMove);
                  targ.dispatchEvent(evOver);
                })(arguments[0], arguments[1]);
            """
            for (x, y), ts in zip(points, timestamps):
                try:
                    driver.execute_script(dispatch_script, int(round(x)), int(round(y)))
                except WebDriverException as e:
                    # ignore occasional failures
                    result.setdefault("js_errors", []).append(str(e))
                pause = random.uniform(pause_jitter[0], pause_jitter[1])
                time.sleep(pause)
                result["points"].append((int(round(x)), int(round(y)), time.time()))

        result["success"] = True
        return result

    except Exception as exc:
        result["error"] = str(exc)
        return result

# def move_over_selector(
#     driver,
#     selector,
#     duration=1.2,
#     steps=12,
#     margin=6,
#     pause_jitter=(0.02, 0.12),
#     use_action_chains=True,
#     wait_timeout=8,
#     seed=None,
# ):
#     """
#     Find element by CSS selector, scroll it into view, wait for presence/visibility,
#     then call human_mouse_move on it.

#     Returns the dict result produced by human_mouse_move.
#     Raises meaningful exceptions on failure.
#     """
#     # Wait for presence (you can change to visibility if you prefer)
#     el = WebDriverWait(driver, wait_timeout).until(
#         EC.presence_of_element_located((By.CSS_SELECTOR, selector))
#     )

#     # If element is present but possibly off-screen, scroll it to center of viewport
#     try:
#         driver.execute_script(
#             "arguments[0].scrollIntoView({block: 'center', inline: 'center', behavior: 'auto'});",
#             el,
#         )
#     except Exception:
#         # fallback: try a simpler scroll
#         try:
#             driver.execute_script("arguments[0].scrollIntoView(true);", el)
#         except Exception:
#             pass

#     # Tiny pause to let layout settle
#     time.sleep(0.18 + (seed or 0) * 0)  # small deterministic-ish pause if seed set

#     # call the existing human_mouse_move function (element preferred)
#     result = human_mouse_move(
#         driver=driver,
#         element=el,
#         duration=duration,
#         steps=steps,
#         margin=margin,
#         pause_jitter=pause_jitter,
#         use_action_chains=use_action_chains,
#         seed=seed,
#     )
#     return result

# def full_path(path:str):
#     return os.path.join(os.getcwd(), path)
def get_top_mp4_groups_with_curl_waudio(driver, top_n=5):
    logger.info("Extracting top MP4 groups with curl commands")
    js = r"""
    return (function getTopNMP4GroupsAsCurl(N) {
      const perf = performance.getEntriesByType("resource")
                     .filter(e => e && e.name && e.name.toLowerCase().includes(".mp4") && (e.transferSize || 0) > 0);
      const entries = perf.map(e => {
        const url = e.name;
        const transferSize = e.transferSize || 0;
        const fnMatch = url.match(/\/([^\/?]+\.mp4)/i);
        const filename = fnMatch ? decodeURIComponent(fnMatch[1]) : (new URL(url)).pathname.split("/").pop();
        return { url, transferSize, filename };
      });
      const grouped = {};
      for (const e of entries) {
        if (!grouped[e.filename]) grouped[e.filename] = { totalSize: 0, urls: [], maxEntry: null };
        grouped[e.filename].totalSize += e.transferSize;
        grouped[e.filename].urls.push(e.url);
        if (!grouped[e.filename].maxEntry || e.transferSize > grouped[e.filename].maxEntry.transferSize) grouped[e.filename].maxEntry = e;
      }
      function getQueryParams(url) {
        try {
          const u = new URL(url);
          const p = {};
          for (const [k,v] of u.searchParams) p[k] = v;
          return p;
        } catch (err) { return {}; }
      }
      function buildCurl(url, filename) {
        const headers = {};
        if (navigator && navigator.userAgent) headers["User-Agent"] = navigator.userAgent;
        const referer = (typeof document !== "undefined" && document.referrer) ? document.referrer : (typeof location !== "undefined" ? location.href : "");
        if (referer) headers["Referer"] = referer;
        if (typeof document !== "undefined" && document.cookie) headers["Cookie"] = document.cookie;
        if (typeof location !== "undefined") headers["Origin"] = location.origin || "";
        headers["Accept"] = "*/*";
        const hdrParts = [];
        for (const [k, v] of Object.entries(headers)) {
          if (v === null || v === undefined || String(v).trim() === "") continue;
          const safe = String(v).replace(/"/g, '\\"');
          hdrParts.push(`-H "${k}: ${safe}"`);
        }
        const headerStr = hdrParts.join(" ");
        const curl = `curl -L "${url}" ${headerStr} --compressed -o "${filename.replace(/"/g, '\\"')}"`;
        return { url, filename, curl, headers };
      }
      // Step 1: build the original results list (video only)
      const results = Object.keys(grouped).map(fn => {
        const data = grouped[fn];
        const primary = data.maxEntry || { url: data.urls[0], transferSize: 0 };
        const videoCurl = buildCurl(primary.url, fn);
        return { 
          filename: fn, 
          totalSize: data.totalSize, 
          urls: data.urls, 
          primaryUrl: primary.url, 
          curl: videoCurl.curl, 
          headers: videoCurl.headers,
          video: videoCurl,
          audio: null
        };
      });
      results.sort((a,b) => b.totalSize - a.totalSize);
      const top = results.slice(0, N);

      // Step 2: find matching audio for those top videos
      for (const item of top) {
        const base = item.filename.replace(/\.mp4$/, "");
        // Find candidate audio entries with same base substring but smaller size
        const audioCandidates = entries.filter(e => 
          e.filename.includes(base) && e.transferSize < (6 * 1024 * 1024)
        );
        if (audioCandidates.length > 0) {
          audioCandidates.sort((a,b) => b.transferSize - a.transferSize);
          const bestAudio = audioCandidates[0];
          item.audio = buildCurl(bestAudio.url, bestAudio.filename);
        }
      }

      return top;
    })(arguments[0]);"""
    return driver.execute_script(js, top_n)

import os
import shlex
import subprocess
import time
import random
from typing import List, Dict, Optional

import os
import re
import random
import subprocess
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

def _set_bytestart_zero(url: str) -> str:
    """
    Return a new URL with query param bytestart=0 and byteend removed.
    If bytestart already exists, set it to 0.
    """
    p = urlparse(url)
    qs = dict(parse_qsl(p.query, keep_blank_values=True))
    # set bytestart to "0" and remove byteend
    qs['bytestart'] = "0"
    qs.pop('byteend', None)
    # Rebuild URL
    new_query = urlencode(qs, doseq=True)
    new_parts = (p.scheme, p.netloc, p.path, p.params, new_query, p.fragment)
    return urlunparse(new_parts)

def _strip_range_header_from_curl(cmd: str) -> str:
    # remove any -H "Range: ..." or -H 'Range: ...'
    return re.sub(r'-H\s+(?:"Range:[^"]*"|\'Range:[^\']*\')\s*', '', cmd, flags=re.IGNORECASE)

def _build_curl_for_entry(url: str, filename: str, headers: Dict[str,str], redact_cookies: bool) -> str:
    """
    Build a curl command for the given url with provided headers and output filename.
    Removes Range header; optionally redacts Cookie header.
    """
    hdr_parts = []
    for k, v in (headers or {}).items():
        if v is None or str(v).strip() == "":
            continue
        if k.lower() == "range":
            # skip Range header (we want full download)
            continue
        if redact_cookies and k.lower() == "cookie":
            continue
        safe_val = str(v).replace('"', '\\"')
        hdr_parts.append(f'-H "{k}: {safe_val}"')
    header_str = " ".join(hdr_parts)
    # Use -L and --compressed like your earlier commands
    curl = f'curl -L "{url}" {header_str} --compressed -o "{filename}"'
    # sanitize multiple spaces
    return re.sub(r'\s+', ' ', curl).strip()

import re
from typing import Dict

import os
import subprocess
import json
import os
import subprocess
import json
import os
import subprocess
import json

def classify_mp4_files(input_folder: str) -> dict:
    """
    Classifies MP4 files in a folder as:
    - 'video_all' (video + audio)
    - 'just_video' (video only)
    - 'just_audio' (audio only)
    - 'unknown' (no audio/video streams found or ffprobe error)

    Files are renamed accordingly.
    If a file already has a classification suffix, it will not be reclassified or renamed.

    Returns:
        dict mapping {original_filename: {"new_name": str, "classification": str}}
    """
    results = {}
    suffixes = {"video_all", "just_video", "just_audio", "unknown"}
    logger.info("Classifying MP4 files in folder: %s", input_folder)
    for filename in os.listdir(input_folder):
        if not filename.lower().endswith(".mp4"):
            continue

        name, ext = os.path.splitext(filename)

        # Skip if already classified
        if any(name.endswith(f"_{s}") for s in suffixes):
            results[filename] = {
                "new_name": filename,
                "classification": name.split("_")[-1]
                if name.split("_")[-1] in suffixes else "unknown"
            }
            continue

        filepath = os.path.join(input_folder, filename)
        classification = "unknown"

        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            filepath
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)

            has_audio = any(s.get("codec_type") == "audio" for s in info.get("streams", []))
            has_video = any(s.get("codec_type") == "video" for s in info.get("streams", []))

            if has_audio and has_video:
                classification = "video_all"
            elif has_video:
                classification = "just_video"
            elif has_audio:
                classification = "just_audio"

        except subprocess.CalledProcessError:
            classification = "unknown"

        # Rename file only once
        new_filename = f"{name}_{classification}{ext}"
        new_filepath = os.path.join(input_folder, new_filename)

        if new_filename != filename:
            os.rename(filepath, new_filepath)

        results[filename] = {
            "new_name": new_filename,
            "classification": classification
        }
    merged_filenames = combine_audio_video([
    os.path.join(input_folder, r['new_name'])
    for r in results.values()
    if r['classification'] in ('just_video', 'just_audio')
])
    # merged_filenames = combine_audio_video([r['new_name'] for r in results.values() if r['classification'] in ('just_video', 'just_audio')])
    logger.info("Merged files: %s", merged_filenames)
    return results


def _build_curl_for_entry_(url: str, filename: str, headers: Dict[str, str], redact_cookies: bool = True) -> str:
    """
    Build a curl command for the given url with provided headers and output filename.
    - Removes Range header (we want full download).
    - Optionally redacts Cookie header.
    - Quotes header values safely.
    - Always overwrites the output file (no resume).
    """
    hdr_parts = []
    for k, v in (headers or {}).items():
        if v is None or str(v).strip() == "":
            continue
        if k.lower() == "range":
            continue  # skip Range header
        if redact_cookies and k.lower() == "cookie":
            continue
        safe_val = str(v).replace('"', '\\"')
        hdr_parts.append(f'-H "{k}: {safe_val}"')

    header_str = " ".join(hdr_parts)

    # Use -L (follow redirects), -sS (silent but show errors), and --compressed
    curl = f'curl -L -sS --compressed "{url}" {header_str} -o "{filename}"'

    # sanitize multiple spaces
    return re.sub(r'\s+', ' ', curl).strip()

def get_first_link_href_base(driver):
    """
    Find the first <a> element inside <main> in the DOM and
    return its href up to and including the second slash.
    Example: href="/folder/page?x=1" -> "/folder/"
    Returns None if not found.
    """
    js = r"""
    return (function() {
      const main = document.querySelector("main");
      if (!main) return null;

      const link = main.querySelector("a");
      if (!link) return null;

      const href = link.getAttribute("href");
      if (!href) return null;

      const firstSlash = href.indexOf("/");
      const secondSlash = href.indexOf("/", firstSlash + 1);

      if (secondSlash === -1) {
        return href;
      }

      return href.slice(0, secondSlash + 1);
    })();
    """
    return driver.execute_script(js)


import os
import random
import subprocess
import logging
from typing import List, Dict, Optional



def write_and_run_full_download_script_(
    video_results: List[Dict],
    config,
    out_script_path: str = "download_full_media.sh",
    redact_cookies: bool = True,
    make_executable: bool = True,
    run_script: bool = False,
    sleep_between: Optional[float] = 1.0,
    rnd_sleep_jitter: float = 0.5,
) -> Dict:
    """
    Write a bash script that downloads full files (bytestart=0) for videos found.
    Saves output media into `config.data.media_path`.
    Returns metadata dict. Optionally runs the script.
    """
    media_dir = os.path.abspath(config.data.media_path)
    os.makedirs(media_dir, exist_ok=True)

    commands = []

    for idx, item in enumerate(video_results):
        video_url = item.get("primaryUrl")
        video_fn = item.get("filename").replace(".mp4", f"_{idx}.mp4") or f"video_{idx}.mp4"
        headers = item.get("headers") or {}

        if video_url:
            fixed_url = _set_bytestart_zero(video_url)
            curl_cmd = _build_curl_for_entry_(
                fixed_url, video_fn, headers, redact_cookies=redact_cookies
            )
            commands.append(curl_cmd)

    # craft script
    header = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f'cd "{media_dir}"',
        'echo "Starting full-file downloads (bytestart=0)..."',
        ""
    ]
    body = []
    for i, cmd in enumerate(commands, start=1):
        body.append(f'echo "---- Running command {i}/{len(commands)} ----"')
        body.append(cmd)
        if sleep_between and sleep_between > 0:
            jitter = random.uniform(-rnd_sleep_jitter, rnd_sleep_jitter)
            sleep_time = max(0.0, float(sleep_between) + jitter)
            body.append(f"sleep {sleep_time:.2f}")
        body.append("")

    script_text = "\n".join(header + body)
    with open(out_script_path, "w", encoding="utf-8") as fh:
        fh.write(script_text)
    if make_executable:
        os.chmod(out_script_path, 0o755)

    result = {
        "script_path": os.path.abspath(out_script_path),
        "commands_written": commands,
        "media_dir": media_dir,
        "run": None
    }

    if run_script:
        proc = subprocess.Popen(
            ["bash", result["script_path"]],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            # log only failures
            logger.error("Download script failed with code %s", proc.returncode)
            if stderr:
                logger.error("stderr:\n%s", stderr.strip())
        result["run"] = {
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr
        }

    return result



def write_and_run_full_download_script(
    video_results: List[Dict],
    out_script_path: str = "download_full_media.sh",
    redact_cookies: bool = True,
    make_executable: bool = True,
    run_script: bool = False,
    sleep_between: Optional[float] = 1.0,
    rnd_sleep_jitter: float = 0.5,
) -> Dict:
    """
    Write a bash script that downloads full files (bytestart=0) for videos & audios found.
    Returns metadata dict. Optionally runs the script.
    """
    commands = []

    for item in video_results:
        # Prefer primaryUrl if available; also allow curl or video.curl
        # We will reconstruct curl using the headers object if present (safer).
        video_entry = None
        if item.get("video") and isinstance(item["video"], dict):
            video_entry = item["video"]
        # fallback shapes
        video_url = item.get("primaryUrl") or (video_entry and video_entry.get("url")) or None
        video_fn = item.get("filename") or (video_entry and video_entry.get("filename")) or "video.mp4"
        headers = item.get("headers") or (video_entry and video_entry.get("headers")) or {}

        if video_url:
            fixed_url = _set_bytestart_zero(video_url)
            # ensure output filename distinct
            out_fn = video_fn
            # remove Range header from provided headers if present
            curl_cmd = _build_curl_for_entry(fixed_url, out_fn, headers, redact_cookies=redact_cookies)
            commands.append(curl_cmd)

        # Handle audio if present
        audio_obj = item.get("audio")
        if audio_obj and isinstance(audio_obj, dict):
            audio_url = audio_obj.get("url")
            audio_fn = audio_obj.get("filename") or f"{video_fn.replace('.mp4','')}_audio.mp4"
            audio_headers = audio_obj.get("headers", headers) or headers
            if audio_url:
                fixed_audio_url = _set_bytestart_zero(audio_url)
                audio_curl_cmd = _build_curl_for_entry(fixed_audio_url, audio_fn, audio_headers, redact_cookies=redact_cookies)
                commands.append(audio_curl_cmd)

    # craft script
    header = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'echo "Starting full-file downloads (bytestart=0)..."',
        ""
    ]
    body = []
    for i, cmd in enumerate(commands, start=1):
        body.append(f'echo "---- Running command {i}/{len(commands)} ----"')
        body.append(cmd)
        if sleep_between and sleep_between > 0:
            jitter = random.uniform(-rnd_sleep_jitter, rnd_sleep_jitter)
            sleep_time = max(0.0, float(sleep_between) + jitter)
            body.append(f"sleep {sleep_time:.2f}")
        body.append("")

    script_text = "\n".join(header + body)
    with open(out_script_path, "w", encoding="utf-8") as fh:
        fh.write(script_text)
    if make_executable:
        os.chmod(out_script_path, 0o755)

    result = {
        "script_path": os.path.abspath(out_script_path),
        "commands_written": commands,
        "run": None
    }

    if run_script:
        proc = subprocess.Popen(["bash", result["script_path"]],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True)
        stdout, stderr = proc.communicate()
        result["run"] = {"returncode": proc.returncode, "stdout": stdout, "stderr": stderr}

    return result


def write_and_run_curl_script(
    video_results: List[Dict],
    out_script_path: str = "download_media.sh",
    make_executable: bool = True,
    run_script: bool = False,
    redact_cookies: bool = True,
    sleep_between: Optional[float] = 1.0,
    rnd_sleep_jitter: float = 0.5,
) -> Dict:
    """
    Write curl commands from get_top_mp4_groups_with_curl output into a bash script.
    Optionally run the script.

    Args:
      video_results: list of dicts returned by get_top_mp4_groups_with_curl(driver, ...)
                     each dict expected to have 'curl' and optionally ['audio']['curl'].
      out_script_path: path to write the shell script.
      make_executable: chmod +x the script after writing.
      run_script: if True, execute the script (synchronously) and return result.
      redact_cookies: if True, remove any -H "Cookie: ..." parts from curl strings for privacy.
      sleep_between: number of seconds between commands (can be 0 or None to skip).
      rnd_sleep_jitter: additional random jitter +/- seconds to add variation.

    Returns:
      dict with keys:
        - script_path
        - commands_written: list of commands written to script
        - run: { returncode, stdout, stderr } if run_script True, else None
    """
    def _redact_cookie_from_curl(curl_cmd: str) -> str:
        if not redact_cookies:
            return curl_cmd
        # crude but effective: remove -H "Cookie: ... " occurrences
        import re
        # handle single or double quoted header values (we expect double quotes from your JS)
        return re.sub(r'-H\s+"Cookie:[^"]*"\s*', '', curl_cmd, flags=re.IGNORECASE)

    commands = []
    for idx, item in enumerate(video_results, start=1):
        # main video curl
        curl_cmd = item.get("curl") or (item.get("video", {}) or {}).get("curl")
        if curl_cmd:
            curl_cmd = _redact_cookie_from_curl(curl_cmd)
            commands.append(curl_cmd)

        # audio (if present)
        audio = item.get("audio")
        if audio:
            audio_curl = audio.get("curl") if isinstance(audio, dict) else None
            if audio_curl:
                audio_curl = _redact_cookie_from_curl(audio_curl)
                commands.append(audio_curl)

    # Build script contents
    header = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        'echo "Starting downloads - commands will run sequentially"',
        ""
    ]
    body = []
    for i, cmd in enumerate(commands, start=1):
        # print helpful info and then run command; wrap in a subshell so failures keep header semantics
        safe_label = f"cmd_{i}"
        body.append(f'echo "---- Running {safe_label} ----"')
        # Keep command as-is; if it contains unescaped newlines, using a heredoc would be necessary.
        body.append(cmd)
        if sleep_between is not None and sleep_between > 0:
            # write a sleep with small random jitter
            jitter = random.uniform(-rnd_sleep_jitter, rnd_sleep_jitter)
            sleep_time = max(0.0, float(sleep_between) + jitter)
            body.append(f"sleep {sleep_time:.2f}")
        body.append("")  # blank line

    script_text = "\n".join(header + body)

    # write file
    with open(out_script_path, "w", encoding="utf-8") as fh:
        fh.write(script_text)

    if make_executable:
        os.chmod(out_script_path, 0o755)

    result = {
        "script_path": os.path.abspath(out_script_path),
        "commands_written": commands,
        "run": None
    }

    # Optionally run it now (synchronously)
    if run_script:
        # Run with bash to use set -euo
        proc = subprocess.Popen(["bash", result["script_path"]],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True)
        stdout, stderr = proc.communicate()
        result["run"] = {
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr
        }

    return result


def get_top_mp4_groups_with_curl(driver, top_n=5):
    js = r"""
    return (function getTopNMP4GroupsAsCurl(N) {
      const perf = performance.getEntriesByType("resource")
                     .filter(e => e && e.name && e.name.toLowerCase().includes(".mp4") && (e.transferSize || 0) > 0);
      const entries = perf.map(e => {
        const url = e.name;
        const transferSize = e.transferSize || 0;
        const fnMatch = url.match(/\/([^\/?]+\.mp4)/i);
        const filename = fnMatch ? decodeURIComponent(fnMatch[1]) : (new URL(url)).pathname.split("/").pop();
        return { url, transferSize, filename };
      });
      const grouped = {};
      for (const e of entries) {
        if (!grouped[e.filename]) grouped[e.filename] = { totalSize: 0, urls: [], maxEntry: null };
        grouped[e.filename].totalSize += e.transferSize;
        grouped[e.filename].urls.push(e.url);
        if (!grouped[e.filename].maxEntry || e.transferSize > grouped[e.filename].maxEntry.transferSize) grouped[e.filename].maxEntry = e;
      }
      function getQueryParams(url) {
        try {
          const u = new URL(url);
          const p = {};
          for (const [k,v] of u.searchParams) p[k] = v;
          return p;
        } catch (err) { return {}; }
      }
      const results = Object.keys(grouped).map(fn => {
        const data = grouped[fn];
        const primary = data.maxEntry || { url: data.urls[0], transferSize: 0 };
        const headers = {};
        if (navigator && navigator.userAgent) headers["User-Agent"] = navigator.userAgent;
        const referer = (typeof document !== "undefined" && document.referrer) ? document.referrer : (typeof location !== "undefined" ? location.href : "");
        if (referer) headers["Referer"] = referer;
        if (typeof document !== "undefined" && document.cookie) headers["Cookie"] = document.cookie;
        if (typeof location !== "undefined") headers["Origin"] = location.origin || "";
        headers["Accept"] = "*/*";
        const params = getQueryParams(primary.url);
        if (params.bytestart !== undefined && params.byteend !== undefined) {
          const bs = params.bytestart;
          const be = params.byteend;
          if (!isNaN(Number(bs)) && !isNaN(Number(be))) {
            headers["Range"] = `bytes=${bs}-${be}`;
          }
        }
        const hdrParts = [];
        for (const [k, v] of Object.entries(headers)) {
          if (v === null || v === undefined || String(v).trim() === "") continue;
          const safe = String(v).replace(/"/g, '\\"');
          hdrParts.push(`-H "${k}: ${safe}"`);
        }
        const headerStr = hdrParts.join(" ");
        const curl = `curl -L "${primary.url}" ${headerStr} --compressed -o "${fn.replace(/"/g, '\\"')}"`;
        return { filename: fn, totalSize: data.totalSize, urls: data.urls, primaryUrl: primary.url, curl };
      });
      results.sort((a,b) => b.totalSize - a.totalSize);
      return results.slice(0, N);
    })(arguments[0]);"""
    return driver.execute_script(js, top_n)

def set_reel_volume(driver, level=0.1):
    """Set reel volume (0.0-1.0)."""
    try:
        driver.execute_script("""
            const vid = document.querySelector("video");
            if (vid) { vid.volume = arguments[0]; vid.muted = false; }
        """, level)
        print(f"✅ Volume set to {level*100:.0f}% and unmuted")
        return True
    except Exception as e:
        print(f"⚠️ Could not set volume: {e}")
        return False
from selenium.common.exceptions import JavascriptException



# def unmute_if_muted(driver: WebDriver, volume: float = 1.0) -> dict:
#     """
#     If the video element is muted, click the site's audio button to unmute.
#     Then set the volume to the desired level.
    
#     Args:
#         driver: Selenium WebDriver
#         volume: float between 0.0 and 1.0 (e.g. 0.5 = 50%, 1.0 = 100%)
    
#     Returns:
#         dict with success flag, logs, and whether a video was found
#     """
#     js_code = f"""
#     return (function() {{
#       const result = {{ success: false, logs: [], videoFound: false }};
#       try {{
#         const vid = document.querySelector("video");
#         if (!vid) {{
#           result.logs.push("No <video> found");
#           return result;
#         }}
#         result.videoFound = true;

#         if (vid.muted) {{
#           const button = document.querySelector('button[aria-label*="Audio"], svg[aria-label*="Audio"]');
#           if (button) {{
#             button.dispatchEvent(new MouseEvent("click", {{ bubbles: true, cancelable: true, view: window }}));
#             result.logs.push("Video was muted → clicked audio button to unmute");
#           }} else {{
#             result.logs.push("Video was muted but no audio button found");
#           }}
#         }} else {{
#           result.logs.push("Video already unmuted → nothing done");
#         }}

#         // Always force volume to desired level
#         vid.muted = false;
#         vid.volume = {volume};
#         result.logs.push("Set video volume to " + Math.round({volume} * 100) + "%");

#         result.success = true;
#       }} catch (e) {{
#         result.logs.push("Error: " + e.toString());
#       }}
#       return result;
#     }})();
#     """
#     return driver.execute_script(js_code)

import os
import subprocess
import json
from typing import List, Dict

def combine_audio_video(file_names: List[str]) -> Dict[str, dict]:
    """
    Matches *_just_audio.mp4 and *_just_video.mp4 files by duration (within 5% margin)
    and merges them into single MP4s with both audio+video.
    
    The merged file is written into the same folder as the inputs with suffix "_merged.mp4".

    Args:
        file_names: list of input filenames (full paths or relative)

    Returns:
        dict mapping "output_file" -> {"audio": audio_file, "video": video_file, "status": str}
    """
    logger.info(f"Combining audio and video files if matching pairs found - {file_names}")
    def get_duration(filepath: str) -> float:
        """Get duration of file in seconds using ffprobe."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        return float(info["format"]["duration"])

    # Separate audio and video files
    audio_files = [f for f in file_names if f.endswith("_just_audio.mp4")]
    video_files = [f for f in file_names if f.endswith("_just_video.mp4")]

    # Collect durations
    audio_info = {f: get_duration(f) for f in audio_files}
    video_info = {f: get_duration(f) for f in video_files}

    results = {}

    # Try to pair files
    for vfile, vdur in video_info.items():
        best_match = None
        best_diff = float("inf")

        for afile, adur in audio_info.items():
            diff = abs(vdur - adur)
            margin = max(vdur, adur) * 0.05  # 5% tolerance

            if diff <= margin and diff < best_diff:
                best_match = afile
                best_diff = diff

        if best_match:
            # Build output file name in same folder
            base_name = os.path.splitext(os.path.basename(vfile))[0].replace("_just_video", "")
            folder = os.path.dirname(vfile) or "."
            output_file = os.path.join(folder, f"{base_name}_merged.mp4")

            # ffmpeg merge command (copy video, re-encode audio if needed)
            cmd = [
                "ffmpeg", "-y",  # overwrite without asking
                "-i", vfile,
                "-i", best_match,
                "-c:v", "copy",
                "-c:a", "aac",
                output_file
            ]

            try:
                subprocess.run(cmd, capture_output=True, check=True)
                results[output_file] = {
                    "audio": best_match,
                    "video": vfile,
                    "status": "merged"
                }
            except subprocess.CalledProcessError as e:
                results[output_file] = {
                    "audio": best_match,
                    "video": vfile,
                    "status": f"ffmpeg error: {e}"
                }

            # Remove used audio file so it doesn't get paired again
            del audio_info[best_match]

    return results


def unmute_if_muted(driver: "WebDriver", volume: float = 1.0) -> dict:
    """
    Ensures a <video> element is unmuted, sets its volume,
    and resumes playback if it was paused due to background throttling.

    Args:
        driver: Selenium WebDriver
        volume: float between 0.0 and 1.0

    Returns:
        dict with success flag, logs, and whether a video was found
    """
    js_code = f"""
    return (function() {{
      const result = {{ success: false, logs: [], videoFound: false }};
      try {{
        const vid = document.querySelector("video");
        if (!vid) {{
          result.logs.push("No <video> element found");
          return result;
        }}
        result.videoFound = true;

        // Normalize volume
        let vol = Math.max(0.0, Math.min(1.0, {volume}));

        if (vid.muted) {{
          const button = document.querySelector(
            'button[aria-label*="Audio"], button[aria-label*="Mute"], button[aria-label*="Unmute"], ' +
            'svg[aria-label*="Audio"], svg[aria-label*="Mute"], svg[aria-label*="Unmute"]'
          );
          if (button) {{
            button.dispatchEvent(new MouseEvent("click", {{ bubbles: true, cancelable: true, view: window }}));
            result.logs.push("Video was muted → clicked button to unmute");
          }} else {{
            result.logs.push("Video was muted but no matching audio control found");
          }}
        }} else {{
          result.logs.push("Video already unmuted → nothing clicked");
        }}

        // Always enforce unmuted state + volume
        vid.muted = false;
        vid.volume = vol;
        result.logs.push("Forced volume to " + Math.round(vol * 100) + "%");

        // Try to resume playback in case browser paused it
        vid.play().then(() => {{
          result.logs.push("Playback resumed successfully");
        }}).catch(e => {{
          result.logs.push("Playback resume blocked: " + e.toString());
        }});

        result.success = true;
      }} catch (e) {{
        result.logs.push("Error: " + e.toString());
      }}
      return result;
    }})();
    """
    return driver.execute_script(js_code)


def unmute_reel(driver, volume_level=0.1):
    """
    Clicks Instagram's SVG-based audio toggle (if present),
    then ensures <video> is unmuted and volume set.
    
    Args:
        driver: Selenium WebDriver
        volume_level: float 0.0-1.0 (e.g. 0.1 = 10%)
    
    Returns:
        dict with success status, logs, and flags.
    """
    js = """
    return (function(volumeLevel) {
      const result = { success: false, logs: [], svgFound: false, buttonClicked: false, videoFound: false };
      try {
        const svg = document.querySelector('svg[aria-label*="Audio"]');
        if (svg) {
          result.svgFound = true;
          const parent = svg.closest("div");
          if (parent) {
            parent.click();
            result.buttonClicked = true;
            result.logs.push("Clicked parent of SVG audio control");
          } else {
            result.logs.push("SVG found but no clickable parent div");
          }
        } else {
          result.logs.push("No SVG with aria-label*='Audio' found");
        }

        const vid = document.querySelector("video");
        if (vid) {
          vid.muted = false;
          vid.volume = volumeLevel;
          result.videoFound = true;
          result.logs.push("Forced video.muted=false, volume=" + Math.round(volumeLevel*100) + "%");
        } else {
          result.logs.push("No <video> found");
        }

        result.success = true;
      } catch (e) {
        result.logs.push("Error: " + e.toString());
      }
      return result;
    })(arguments[0]);
    """
    try:
        return driver.execute_script(js, float(volume_level))
    except JavascriptException as e:
        return {"success": False, "logs": [f"JS execution error: {e}"], "svgFound": False, "buttonClicked": False, "videoFound": False}



import json

def find_audio_for_videos(driver, video_results):
    """
    For each video result (from get_top_mp4_groups_with_curl),
    try to find a matching audio/mp4 request in the Selenium performance logs.
    
    Args:
        driver: Selenium WebDriver (with performance logging enabled).
        video_results: List of dicts returned by get_top_mp4_groups_with_curl.
    
    Returns:
        A list of dicts with both video + audio curl data when available.
    """
    logs = driver.get_log("performance")

    # Extract all network responses with mimeType
    audio_map = {}
    for entry in logs:
        try:
            msg = json.loads(entry["message"])["message"]
            if msg.get("method") != "Network.responseReceived":
                continue
            resp = msg["params"]["response"]
            url = resp.get("url", "")
            mime = resp.get("mimeType", "")
            if mime == "audio/mp4":
                # Extract base filename for grouping
                fn_match = url.split("/")[-1].split("?")[0]
                audio_map[fn_match] = url
        except Exception:
            continue

    results = []
    for video in video_results:
        filename = video["filename"]
        base = filename.replace(".mp4", "")

        # Find matching audio with same base key
        audio_url = None
        for cand_fn, cand_url in audio_map.items():
            if base in cand_fn:
                audio_url = cand_url
                break

        if audio_url:
            # Reuse headers from video curl for consistency
            headers = video.get("headers", {})
            hdr_parts = []
            for k, v in headers.items():
                if v is None or str(v).strip() == "":
                    continue
                safe = str(v).replace('"', '\\"')
                hdr_parts.append(f'-H "{k}: {safe}"')
            header_str = " ".join(hdr_parts)
            audio_curl = f'curl -L "{audio_url}" {header_str} --compressed -o "{base}_audio.mp4"'
            video["audio"] = {
                "url": audio_url,
                "curl": audio_curl,
                "filename": f"{base}_audio.mp4",
            }
        else:
            video["audio"] = None

        results.append(video)

    return results



### GPT optmized functions
import random
import time
import logging
import hashlib
import math
from typing import Callable, List, Tuple, Dict, Optional

import numpy as np
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver, WebElement
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# -------------------------
# Helper: human_like_click
# -------------------------
def human_like_click_gpt(driver: WebDriver, element: WebElement, actions: Optional[ActionChains] = None, max_retries: int = 3) -> bool:
    """
    Try to click element in human-like way: ActionChains move + perform, fallback to JS dispatch,
    with simple retries. Return True if click or synthetic click was issued.
    """
    actions = actions or ActionChains(driver)
    for attempt in range(max_retries):
        try:
            # Try move then click
            actions.move_to_element(element).pause(0.02 + random.random() * 0.05).click().perform()
            return True
        except WebDriverException as e:
            logger.debug(f"ActionChains click attempt {attempt} failed: {e}")
            time.sleep(0.05 * (attempt + 1))
            try:
                # Fallback: dispatch pointer/mouse events at element center via JS
                rect = driver.execute_script(
                    "const r=arguments[0].getBoundingClientRect();"
                    "return {cx: Math.round(r.left + r.width/2), cy: Math.round(r.top + r.height/2)};",
                    element,
                )
                if rect and "cx" in rect:
                    driver.execute_script(
                        """
                        (function(cx, cy){
                          const targ = document.elementFromPoint(cx, cy) || document.body;
                          ['mouseover','mousemove','mousedown','mouseup','click'].forEach(name => {
                              const ev = new MouseEvent(name, {bubbles:true, cancelable:true, clientX:cx, clientY:cy});
                              targ.dispatchEvent(ev);
                          });
                        })(arguments[0], arguments[1]);
                        """,
                        int(rect["cx"]),
                        int(rect["cy"]),
                    )
                    return True
            except Exception as js_e:
                logger.debug(f"JS fallback click attempt {attempt} failed: {js_e}")
                time.sleep(0.03)
    logger.warning("human_like_click: all attempts failed.")
    return False


# -------------------------
# Robust improved JS for detecting mp4s and building curl commands
# -------------------------
def get_top_mp4_groups_with_curl_gpt(driver: WebDriver, top_n: int = 5, target_profile: Optional[str] = None):
    """
    Uses performance entries to find .mp4 resources, groups them, and returns
    a list sorted by total transferSize with curl commands. Filters blob: and
    requires http(s) urls. Adds a short hash to filename and optional target_profile.
    ALWAYS returns a Python list (possibly empty).
    """
    safe_profile = target_profile or "profile"
    js = r"""
    return (function getTopNMP4GroupsAsCurl(N, targetProfile) {
      function safeStartsHttp(s){return typeof s === 'string' && (s.startsWith('http://') || s.startsWith('https://'));}
      const resources = (performance.getEntriesByType ? performance.getEntriesByType("resource") : [])
        .filter(e => e && e.name && safeStartsHttp(e.name) && e.name.toLowerCase().includes(".mp4"));

      const entries = resources.map(e => {
        const url = e.name;
        const transferSize = e.transferSize || 0;
        let fnMatch=null;
        try{ fnMatch = url.match(/\/([^\/?]+\.mp4)(?:[?#].*)?$/i); }catch(_){}
        const filename = fnMatch ? decodeURIComponent(fnMatch[1]) : (new URL(url)).pathname.split("/").pop();
        return { url, transferSize, filename };
      });

      const grouped = {};
      for (const e of entries) {
        const key = e.filename || e.url;
        if (!grouped[key]) grouped[key] = { totalSize: 0, urls: [], maxEntry: null };
        grouped[key].totalSize += e.transferSize;
        grouped[key].urls.push(e.url);
        if (!grouped[key].maxEntry || e.transferSize > grouped[key].maxEntry.transferSize) grouped[key].maxEntry = e;
      }

      function minimalCookies() {
        // keep only likely needed cookies (sessionid, csrftoken) to avoid exposing everything
        try {
          if (!document || !document.cookie) return '';
          return document.cookie.split(';').map(s => s.trim()).filter(s => s.startsWith('sessionid=') || s.startsWith('csrftoken=')).join('; ');
        } catch(e){ return ''; }
      }

      const cookieStr = minimalCookies();
      const results = Object.keys(grouped).map(fn => {
        const data = grouped[fn];
        const primary = data.maxEntry || { url: data.urls[0], transferSize: 0 };
        const headers = {};
        try { headers["User-Agent"] = navigator.userAgent || ""; } catch(e){}
        try { headers["Referer"] = document.referrer || location.href || ""; } catch(e){}
        try { headers["Origin"] = location.origin || ""; } catch(e){}
        headers["Accept"] = "*/*";
        if (cookieStr) headers["Cookie"] = cookieStr;

        // compose header parts for curl
        const hdrParts = [];
        for (const [k,v] of Object.entries(headers)) {
          if (v === null || v === undefined) continue;
          const vs = String(v).trim();
          if (!vs) continue;
          hdrParts.push(`-H "${k}: ${vs.replace(/"/g,'\\"')}"`);
        }
        const headerStr = hdrParts.join(" ");
        // add short hash to filename to avoid collisions, include targetProfile hint
        function shortHash(s){
          try { return btoa(unescape(encodeURIComponent(s))).replace(/[^A-Za-z0-9]/g,'').slice(0,8); } catch(e){ return '';}
        }
        const hash = shortHash(primary.url);
        const profilePart = targetProfile ? ('_' + targetProfile.replace(/[^A-Za-z0-9-_]/g,'').slice(0,16)) : '';
        const safeName = (hash ? (hash + '_') : '') + fn;
        const curl = `curl -L "${primary.url}" ${headerStr} --compressed -o "${safeName.replace(/"/g,'\\"')}"`;
        return { filename: safeName, totalSize: data.totalSize, urls: Array.from(new Set(data.urls)), primaryUrl: primary.url, curl };
      });

      results.sort((a,b) => (b.totalSize||0) - (a.totalSize||0));
      return results.slice(0, N);
    })(arguments[0], arguments[1]);"""
    try:
        return driver.execute_script(js, top_n, safe_profile) or []
    except WebDriverException as e:
        logger.warning(f"get_top_mp4_groups_with_curl JS execution failed: {e}")
        return []


# -------------------------
# Improved video src collector (skips blob:)
# -------------------------
def get_all_video_srcs_gpt(driver: WebDriver) -> List[str]:
    """
    Returns list of unique video src URLs (http/https). Skips blob: URIs.
    """
    js = """
    function collectAllVideoSrcs(){
      const srcSet = new Set();
      document.querySelectorAll("video").forEach(video => {
        const add = (u) => { if (u && (u.startsWith('http://') || u.startsWith('https://'))) srcSet.add(u); };
        try {
          if (video.currentSrc) add(video.currentSrc);
          if (video.src) add(video.src);
          video.querySelectorAll("source").forEach(s => add(s.src));
        } catch(e){}
      });
      return Array.from(srcSet);
    }
    return collectAllVideoSrcs();
    """
    try:
        return driver.execute_script(js) or []
    except WebDriverException as e:
        logger.debug(f"get_all_video_srcs failed: {e}")
        return []


# -------------------------
# Robust image gatherer (avoid fragile classnames)
# -------------------------
def get_all_post_images_data_gpt(driver: WebDriver) -> List[Dict]:
    """
    More robust extraction of image attributes from an Instagram post.
    - Look inside article, figure, divs for <img> tags
    - Filter by visible images (bounding rect area > 0)
    - Deduplicate by src
    """
    js_code = r"""
    (function(){
      const imgs = [];
      const seen = new Set();
      const candidates = Array.from(document.querySelectorAll('article img, div img, figure img'));
      for (const img of candidates) {
        try {
          const src = img.getAttribute('src') || img.currentSrc || '';
          if (!src) continue;
          if (seen.has(src)) continue;
          // visibility check: bounding box
          const r = img.getBoundingClientRect();
          if (!r || (r.width <= 0 && r.height <= 0)) continue;
          seen.add(src);
          imgs.push({
            src,
            alt: img.getAttribute('alt') || null,
            title: img.getAttribute('title') || null,
            aria_label: img.getAttribute('aria-label') || null,
            naturalWidth: img.naturalWidth || null,
            naturalHeight: img.naturalHeight || null
          });
        } catch(e){}
      }
      return imgs;
    })();
    """
    try:
        results = driver.execute_script(js_code) or []
        if not results:
            # optionally warn if nothing found using older class approach
            logger.warning("get_all_post_images_data: no images found with robust selector - fallback classes may be missing.")
        return results
    except WebDriverException as e:
        logger.warning(f"get_all_post_images_data JS error: {e}")
        return []


# -------------------------
# Scrape carousel with robustness
# -------------------------
def scrape_carousel_images_gpt(
    driver: WebDriver,
    image_gather_func: Callable[[WebDriver], List[Dict]],
    min_wait: float = 0.5,
    max_wait: float = 2.2,
    max_steps: int = 12
) -> Tuple[List[Dict], List[str]]:
    """
    Iterate through Instagram carousel by clicking Next and collecting images.
    Returns (image_data_list, unique_video_srcs_list).
    Guarantees consistent return types and includes protections:
     - clickable check (element_to_be_clickable)
     - disabled/aria-disabled checks
     - max_steps safety cap
     - log-normal wait distribution between clicks
     - dedup by src
    """
    logger.info("Starting carousel image scrape.")
    image_data: List[Dict] = []
    seen_srcs = set()
    video_srcs = set()
    image_video_map = []
    wait = WebDriverWait(driver, 6)
    actions = ActionChains(driver)
    steps = 0

    def human_delay():
        # log-normal: short most of the time, rare longer pauses
        val = float(np.random.lognormal(mean=0.0, sigma=0.6))
        # clamp to reasonable range
        return max(min_wait, min(max_wait, val))

    while True:
        # collect images & video srcs for current view
        try:
            unmute_if_muted(driver, volume=0.2)
            new_items = image_gather_func(driver) or []
        except Exception as e:
            logger.debug(f"image_gather_func threw: {e}")
            new_items = []

        try:
            new_video_srcs = get_all_video_srcs(driver)
            video_srcs.update(new_video_srcs)
            logger.debug(
                f"Step {steps}: Found {len(new_items)} potential images and "
                f"{len(new_video_srcs)} video sources. "
                f"Total unique video sources: {len(video_srcs)}."
            )
        except Exception as e:
            logger.debug(f"get_all_video_srcs error: {e}")

        map_item = [new_items, list(new_video_srcs)]
        if map_item not in image_video_map:
            image_video_map.append(map_item)
        # Deduplicate by src
        added_count = 0
        for item in new_items:
            src = item.get("src")
            if not src:
                continue
            if src not in seen_srcs:
                seen_srcs.add(src)
                image_data.append(item)
                added_count += 1
        if added_count:
            logger.debug(f"Step {steps}: Added {added_count} new images (total {len(image_data)}).")

        # find Next button: prefer clickable and visible
        if steps >= max_steps:
            logger.info(f"Reached safety max_steps={max_steps}, stopping carousel iteration.")
            break

        try:
            next_button = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label='Next']")))
        except TimeoutException:
            # No Next button at all
            logger.info(f"No 'Next' button present at step {steps}. Ending carousel.")
            break
        except Exception as e:
            logger.debug(f"Next button presence check error: {e}")
            break

        # ensure it's visible/clickable and not disabled
        try:
            # small check for attributes indicating disabled
            disabled_attr = (next_button.get_attribute("disabled") or next_button.get_attribute("aria-disabled") or "").lower()
            if disabled_attr in ("true", "1", "disabled"):
                logger.info("Next button is disabled - end of carousel.")
                break

            # element_to_be_clickable is sometimes stricter; try it but allow fallback
            clickable = True
            try:
                clickable_el = WebDriverWait(driver, 1).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Next']")))
                clickable = clickable_el is not None
            except Exception:
                clickable = False

            if not clickable:
                logger.debug("Next button present but not clickable; attempting human-like click fallback.")
        except Exception as e:
            logger.debug(f"Error checking next_button attributes: {e}")

        # try to click
        clicked = human_like_click_gpt(driver, next_button, actions=actions)
        if not clicked:
            logger.warning(f"Could not click 'Next' button at step {steps} — stopping to avoid infinite loop.")
            break

        steps += 1
        # wait human-like period (bounded to min/max)
        time.sleep(human_delay())

    logger.info(f"Finished carousel scrape after {steps} steps. Found {len(image_data)} unique images and {len(video_srcs)} video sources.")
    return image_data, list(video_srcs),image_video_map


# -------------------------
# media_from_post (consistent returns, robust)
# -------------------------
def media_from_post_gpt(driver: WebDriver) -> Tuple[List[Dict], List[Dict]]:
    """
    Unified media extraction entrypoint. Returns (images_list, videos_list).
    images_list: List[dict] with image attrs
    videos_list: List[dict] with video metadata (from get_top_mp4_groups_with_curl)
    """
    try:
        imgs, video_srcs,img_vid_map = scrape_carousel_images_gpt(driver, get_all_post_images_data)
        if not imgs and not video_srcs:
            logger.info("No carousel media found; trying single-media fallback.")
            single = get_first_img_attributes_in_div(driver)  # assume exists in your codebase
            return ([single] if single else []), [],[]

        # attempt to get full video metadata (curl commands) if video srcs present
        video_data = []
        if video_srcs:
            try:
                # pass target_profile to enrich filenames
                video_data = get_top_mp4_groups_with_curl(driver, top_n=len(video_srcs)*4)
            except Exception as e:
                logger.warning(f"get_top_mp4_groups_with_curl failed: {e}")
                video_data = []

        return imgs, video_data, img_vid_map

    except Exception as e:
        logger.error(f"media_from_post failed: {e}", exc_info=True)
        return [], [], []


# -------------------------
# Example fallback: get_first_img_attributes_in_div
# (simple, safe)
# -------------------------
def get_first_img_attributes_in_div_gpt(driver: WebDriver) -> Optional[Dict]:
    """
    Simple fallback to grab the first <img> inside an article or div for single media posts.
    """
    try:
        js = r"""
        (function(){
          const sel = document.querySelector('article img, div img, figure img');
          if (!sel) return null;
          return {
            src: sel.getAttribute('src') || sel.currentSrc || null,
            alt: sel.getAttribute('alt') || null,
            title: sel.getAttribute('title') || null,
            naturalWidth: sel.naturalWidth || null,
            naturalHeight: sel.naturalHeight || null
          };
        })();
        """
        return driver.execute_script(js)
    except WebDriverException as e:
        logger.debug(f"get_first_img_attributes_in_div error: {e}")
        return None

"""
Notes from GPT
Notes & integration tips

target_profile is used inside the mp4 JS to add a short profile hint to filenames to avoid collisions. Pass self.config.get('target_profile') or similar when calling media_from_post.

I intentionally return ([], []) on any failure to keep return shapes consistent — callers won’t crash.

I kept get_top_mp4_groups_with_curl conservative: it does not attempt to fetch range headers. You said you'd handle partial chunk assembly externally — good.

get_all_post_images_data uses a robust selector set and checks visibility; I left a warning log when the result is empty so you can monitor if IG classes changed.

human_like_click uses both ActionChains and JS event dispatch fallback with retries, which should handle most IG quirks.

scrape_carousel_images enforces a max_steps safety cap and checks for disabled Next button attributes to avoid infinite loops.

Nice — below I’ll walk through **every function** in the module and list **exactly what I changed, why I changed it, and any caveats**. No fluff — just actionable notes so you know where to look and what to expect when you drop this into your codebase.

---

# `human_like_click(driver, element, actions=None, max_retries=3)`

**What I changed**

* Added **retry loop** around click attempts (up to `max_retries`) so transient ActionChains failures don't abort flow.
* First attempt uses `ActionChains.move_to_element(...).pause(...).click().perform()` to simulate human approach + click.
* On failure, added a **JS fallback** that dispatches the sequence `mouseover` → `mousemove` → `mousedown` → `mouseup` → `click` at the element center.
* Added debug logging for each attempt and a final warning if all attempts fail.
* Returns `True/False` reliably (no silent exceptions).

**Why**

* Instagram DOM or overlays often cause ActionChains clicks to fail; the JS fallback lets you still trigger events.
* Retry + short backoff reduces flakiness.

**Caveats**

* JS fallback dispatches synthetic events — in some cases IG may require "real" input to trigger certain handlers (rare). We still attempt ActionChains first.

---

# `get_top_mp4_groups_with_curl(driver, top_n=5, target_profile=None)`

**What I changed**

* Rewrote JS executed in the browser to be **safer and more robust**:

  * Filtered `performance.getEntriesByType("resource")` for `http(s)` URLs only and `.mp4` (skips `blob:`).
  * Group resources by **base filename**, accumulate `transferSize`, and keep the largest entry as the primary.
  * **Minimal cookies**: only include `sessionid` and `csrftoken` instead of entire `document.cookie`.
  * Compose `curl` command including safe headers (`User-Agent`, `Referer`, `Origin`, `Accept`) and minimal cookie string.
  * Add a **short hash** prefix to filename and include sanitized `target_profile` (to avoid collisions).
  * Ensure function always returns a list (possibly empty) and sorts by total transfer size.
* Wrapped `driver.execute_script` in `try/except` and return `[]` on JS/runtime failure (log warning).

**Why**

* Avoid leaking full cookies unnecessarily.
* Avoid `blob:` and ephemeral/local URLs.
* Filename collisions are common — short hash + profile reduces collisions.
* Returning consistent empty list on failure prevents callers from crashing.

**Caveats**

* I intentionally did **not** assemble full file from byte ranges (you said you’ll handle that in Celery). The `curl` targets the primary URL only; if the resource was retrieved via segmented requests, additional work is needed (you planned that).

---

# `get_all_video_srcs(driver)`

**What I changed**

* JS now collects `video.currentSrc`, `video.src`, and all `<source>` `src` attributes, but **only includes http/https** URLs (skips `blob:`).
* Wrapped execution in `try/except` and return `[]` on failure.
* Returns a **deduplicated list** of video URLs.

**Why**

* Avoid `blob:` or inline blob URIs which are ephemeral and cannot be fetched by curl.
* Simpler output shape and more robust against weird DOM states.

**Caveats**

* If Instagram uses signed URLs that expire extremely quickly, you might still get URLs that fail later — but this function reduces the noise.

---

# `get_all_post_images_data(driver)`

**What I changed**

* Replaced fragile `ul._acay > li._acaz > img` logic with a **robust selector**:

  * Query for `article img`, `div img`, `figure img` as candidates.
  * Check **visibility** with `getBoundingClientRect()` (skip zero-area images).
  * Deduplicate by `src`.
  * Return image dicts with `src`, `alt`, `title`, `aria_label`, `naturalWidth`, `naturalHeight`.
* If nothing found, log a **warning** so you can detect when selectors break.
* Wrapped in `try/except` and return `[]` on JS error.

**Why**

* Instagram class names change; broader selection + visibility check reduces breakage.
* Warning gives early detection instead of silent failures.

**Caveats**

* A very different DOM change (IG rewiring image container) might still fail; warning helps you monitor that.

---

# `scrape_carousel_images(driver, image_gather_func, min_wait=0.5, max_wait=2.2, max_steps=25, target_profile=None)`

**What I changed**

* **Consistent return type**: always returns `(image_data_list, video_srcs_list)` (never mixed types).
* **Safety cap (`max_steps`)** to avoid infinite loops when Next button bad or sticky.
* **Presence → clickable** checks:

  * First `presence_of_element_located` (fast detection).
  * Inspect `disabled` / `aria-disabled` attributes to detect when the Next button is present but disabled.
  * Attempt `element_to_be_clickable` briefly; if not clickable, continue with human-like click fallback.
* **human\_delay()** uses a **log-normal** distribution to produce human-like waits bounded by `min_wait`/`max_wait`.
* When collecting images: deduplicate via `seen_srcs` (set) and log number of new images added per step.
* On click failure, break to avoid getting stuck; logs warning.
* Calls `get_all_video_srcs` and dedupes into a set.
* Wrapped all JS calls in try/except and handle errors gracefully (no crashes).
* Added debug/info logs at key points (start, each step, finished step count).

**Why**

* `Next` button can exist but be disabled — need to detect it to terminate.
* Instagram sometimes leaves stale DOM; max steps prevents infinite loops.
* Log-normal wait better mimics real human timing.
* Consistent return types simplify downstream code.

**Caveats**

* If IG changes the `aria-label` of the Next button, presence check might fail; we log a message if no images found so you can detect it.

---

# `media_from_post(driver, target_profile=None)`

**What I changed**

* Unified entrypoint that **always** returns `(images_list, videos_list)`.
* Calls `scrape_carousel_images(...)` and then:

  * If both lists empty: try `get_first_img_attributes_in_div` fallback and return `([single_img], [])` or `([], [])`.
  * If `video_srcs` present, call `get_top_mp4_groups_with_curl` (wrapped in try/except).
* Catch-all try/except around flow to return `([], [])` on unexpected exceptions (and log stack trace).

**Why**

* Prevents inconsistent return shapes and uncaught exceptions propagating out of the media extraction pipeline.
* Centralizes calls to video extractor and handles failures gracefully.

**Caveats**

* `get_top_mp4_groups_with_curl` depends on browser perf timing being available and browser run state.

---

# `get_first_img_attributes_in_div(driver)`

**What I changed**

* Simple, robust fallback to return the first visible image inside `article/div/figure`.
* Returns a single image dict or `None`.
* Wrapped in `try/except` and logs debug on error.

**Why**

* If carousel logic misses everything, this provides a graceful single-image fallback.

**Caveats**

* If the post is video-only, result will be `None`. Caller handles with consistent return types.

---

# Cross-cutting changes (general)

**What I changed across the file**

* **Consistent return types** for all media functions — caller never needs to special-case dict vs list.
* **Defensive programming**: `try/except` around all `execute_script` calls, fallback behavior, and logging for visibility.
* **Security/privacy & hygiene**: minimal cookie exposure in curls (`sessionid` + `csrftoken` only), and hashes in filenames to avoid collisions.
* **Human-like timing**: log-normal delays instead of flat uniform random for better natural rhythm.
* **Retry and fallback strategy** everywhere UI interactions may fail (ActionChains → JS).
* **No silent failures**: functions either return a safe empty structure or `False`/`None` so you can detect and act on issues.
* **Instrumentation**: added helpful `logger.debug/info/warning` messages so you can monitor what the scraper saw and why it stopped.

---

# Small implementation notes & how to integrate

* Pass `target_profile` (e.g., `self.config.get("target_profile")`) into `media_from_post(...)` so the MP4 filenames include the profile hint.
* If you have a global `np` import requirement, ensure `numpy` is available in runtime; I used `np.random.lognormal` (small dependency).
* The `get_top_mp4_groups_with_curl` returns `curl` strings; be careful when executing them — they include cookies and UA headers (you said you delete cookies later).
* `human_like_click` returns `False` when click could not be issued; `scrape_carousel_images` stops at that point to avoid stuck loops.
* Logs are intentionally verbose so you can see edge cases that warrant rule tweaks (e.g., when `get_all_post_images_data` returns empty — check selector).

---

# Quick checklist of fixed items you requested

1. Range header handling — you said you'll do that separately: I left curl without range and added note.
2. Duplicate/ephemeral URLs — filtered `blob:` and deduped.
3. Cookie privacy — minimal cookies included.
4. Filename collisions — added short hash + `target_profile` hint.
5. Transfer size — you’ll restart browser; code sorts by `transferSize` but is robust even if it’s imperfect.
6. Error handling — wrapped JS & driver calls in try/except everywhere.
7. Return shapes — consistent `(list, list)` across functions.
8. `get_top_mp4_groups_with_curl` — improved per your request.
9. CSS selectors fragile — replaced fragile selectors with robust ones and added warning when none found.
10. Clicking `Next` — added clickable/disabled checks + human-like click fallback.
11. End condition — `max_steps` and disabled checks to avoid infinite loops.
12. Timing randomness — switched to log-normal distribution bounded by `min_wait`/`max_wait`.

---

# Final caveats & suggestions

* Keep an eye on logs for the first few days after deployment — IG DOM changes are the most likely breakage point; the warnings I added are there to alert you quickly.
* If you run the browser headless, verify `performance.getEntriesByType` actually contains entries in your environment — sometimes privacy flags or timing contexts differ.
* If you want even more resilience, consider adding a **DOM snapshot** fallback: when extraction fails, snapshot `document.documentElement.outerHTML` and save it for offline debugging.
* If you plan to share the `curl` commands or store them, make sure you scrub sensitive tokens afterward.

---

If you want I can:

* inject these changes into your `self`/class context and adapt logging to your logger object, or
* produce a minimal test harness that runs against a saved Instagram post HTML (offline) to validate selectors without hitting IG live.

Which one should I produce next?

"""


import math
import os
import random
import time
import requests
from typing import Optional, Generator, Tuple, List, Dict

KB = 1024
MB = 1024 * KB

# Seed RNG once per worker to decorrelate Celery/parallel workers
random.seed(os.urandom(8))


def _rand_int_around(base: int, pct: float) -> int:
    """Return an int near base within ±pct (e.g. pct=0.10 for ±10%)."""
    low = math.floor(base * (1.0 - pct))
    high = math.ceil(base * (1.0 + pct))
    return random.randint(max(0, low), max(0, high))


def discover_total_size(url: str,
                        headers: Optional[Dict[str, str]] = None,
                        session: Optional[requests.Session] = None,
                        timeout: float = 10.0) -> Tuple[Optional[int], Dict[str, str]]:
    """
    Try HEAD to find Content-Length and Accept-Ranges.
    Returns (total_size or None, response.headers).
    Falls back cleanly if HEAD not allowed.
    """
    s = session or requests.Session()
    try:
        resp = s.head(url, headers=headers or {}, allow_redirects=True, timeout=timeout)
        if resp.status_code in (405, 403):
            return None, {}
        ch = resp.headers
        length = ch.get("Content-Length") or ch.get("content-length")
        total = int(length) if length is not None else None
        return total, dict(ch)
    except Exception:
        return None, {}


def generate_ranges(total_size: Optional[int] = None) -> Generator[Tuple[int, int], None, None]:
    """
    Generate (start, end) byte ranges according to your policy:
      - first chunk: 0 -> ~959 (±10%)
      - second chunk: ~2MB (±5%)
      - subsequent chunks: ~4MB (±5%) until end (if known) or indefinite if unknown
    """
    initial_end = _rand_int_around(959, 0.10)
    yield 0, initial_end
    start = initial_end + 1

    two_mb_size = _rand_int_around(2 * MB, 0.05)
    end = start + two_mb_size - 1
    if total_size is not None and end >= total_size:
        yield start, total_size - 1
        return
    yield start, end
    start = end + 1

    while True:
        four_mb_size = _rand_int_around(4 * MB, 0.05)
        end = start + four_mb_size - 1
        if total_size is not None:
            if start > total_size - 1:
                break
            if end >= total_size:
                yield start, total_size - 1
                break
            yield start, end
            start = end + 1
        else:
            yield start, end
            start = end + 1


def fetch_with_ranges(
    url: str,
    base_headers: Optional[Dict[str, str]] = None,
    out_path: Optional[str] = None,
    session: Optional[requests.Session] = None,
    trust_head: bool = True,
    max_chunks: Optional[int] = None,
    timeout: float = 20.0,
    stream_chunk_save: bool = True,
    max_retries: int = 3,
) -> List[Dict]:
    """
    Perform ranged fetches according to the plan.
    Returns list of dicts with metadata for each request.
    """
    s = session or requests.Session()
    base_headers = dict(base_headers or {})

    total = None
    if trust_head:
        total, _ = discover_total_size(url, base_headers, session=s)

    results = []
    chunk_iter = generate_ranges(total_size=total)

    for idx, (start, end) in enumerate(chunk_iter, start=1):
        if max_chunks is not None and idx > max_chunks:
            break

        rng = f"bytes={start}-{end}"
        hdrs = base_headers.copy()
        hdrs["Range"] = rng

        # open file for first chunk in wb, later in ab
        out_fh = None
        if out_path:
            mode = "wb" if idx == 1 else "ab"
            out_fh = open(out_path, mode)

        try:
            # retry loop per chunk
            resp = None
            for attempt in range(max_retries):
                try:
                    resp = s.get(url, headers=hdrs, stream=True, allow_redirects=True, timeout=timeout)
                    break
                except requests.RequestException as e:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(0.5 * (attempt + 1))

            if resp is None:
                raise RuntimeError("Failed to fetch chunk after retries")

            meta = {
                "idx": idx,
                "start": start,
                "end": end,
                "requested_range": rng,
                "status_code": resp.status_code,
                "received_len": 0,
                "server_headers": dict(resp.headers),
            }

            # If server ignored range (200)
            if resp.status_code == 200:
                data_len = 0
                if stream_chunk_save:
                    for chunk in resp.iter_content(8192):
                        if chunk:
                            data_len += len(chunk)
                            if out_fh:
                                out_fh.write(chunk)
                else:
                    body = resp.content
                    data_len = len(body)
                    if out_fh:
                        out_fh.write(body)

                meta["received_len"] = data_len
                results.append(meta)

                # If first request got full file -> done
                if start == 0:
                    break
                else:
                    # ranges unsupported, stop to avoid re-downloading
                    break

            elif resp.status_code == 206:  # partial OK
                data_len = 0
                if stream_chunk_save:
                    for chunk in resp.iter_content(8192):
                        if chunk:
                            data_len += len(chunk)
                            if out_fh:
                                out_fh.write(chunk)
                else:
                    data = resp.content
                    data_len = len(data)
                    if out_fh:
                        out_fh.write(data)

                meta["received_len"] = data_len

                # Content-Range sanity
                cr = resp.headers.get("Content-Range")
                if cr and "bytes" in cr:
                    try:
                        units, rng_part, total_str = cr.split()
                        cr_start, cr_end = [int(x) for x in rng_part.split("-")]
                        meta["server_range"] = (cr_start, cr_end)
                        meta["content_total"] = int(total_str) if "/" in cr else None
                        if cr_start != start or cr_end != end:
                            meta["range_mismatch"] = True
                    except Exception:
                        meta["range_parse_error"] = cr

                results.append(meta)

                requested_len = end - start + 1
                if data_len < requested_len:
                    break  # short read = end of file
                continue

            else:
                results.append(meta)
                if resp.status_code in (416, 404):
                    break
                break

        finally:
            if out_fh:
                out_fh.close()

    return results


import json
import base64
import gzip
import brotli
import zstandard as zstd
from typing import List, Dict, Any

def decode_body(body_dict, headers, request_id, url) -> dict | None:
    """Decode response body based on headers and return JSON if possible."""
    raw_body = body_dict.get("body")
    if raw_body is None:
        print(f"[{request_id}] {url} → No body found")
        return None

    # Handle base64-encoded bodies
    if body_dict.get("base64Encoded"):
        print(f"[{request_id}] {url} → Base64 decoding")
        raw_body = base64.b64decode(raw_body)
    elif isinstance(raw_body, str):
        # If it's a plain JSON string already
        try:
            print(f"[{request_id}] {url} → Direct JSON parse")
            return json.loads(raw_body)
        except Exception:
            raw_body = raw_body.encode("utf-8")

    # At this point, raw_body is bytes
    encoding = headers.get("content-encoding", "").lower()

    # Try plain JSON first
    try:
        print(f"[{request_id}] {url} → Attempting raw JSON decode")
        return json.loads(raw_body.decode("utf-8"))
    except Exception:
        print(f"[{request_id}] {url} → Raw decode failed, checking encoding={encoding}")

    # Fall back to decompressing if JSON fails
    try:
        if "gzip" in encoding:
            print(f"[{request_id}] {url} → Decompressing gzip")
            raw_body = gzip.decompress(raw_body)
        elif "br" in encoding:
            print(f"[{request_id}] {url} → Decompressing brotli")
            raw_body = brotli.decompress(raw_body)
        elif "zstd" in encoding:
            print(f"[{request_id}] {url} → Decompressing zstd")
            dctx = zstd.ZstdDecompressor()
            raw_body = dctx.decompress(raw_body)
        else:
            print(f"[{request_id}] {url} → Unknown encoding, skipping")
            return None

        return json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        print(f"[{request_id}] {url} → Decompression/JSON parse failed: {e}")
        return None

import json
from typing import List, Dict, Any

def get_shortcode_web_info(driver) -> List[Dict[str, Any]]:
    """
    Extract Instagram GraphQL responses that contain 'data'.
    Logs requestId, URL, and the first 2 keys inside 'data'.
    Returns list of {requestId, url, data, data_keys, status, extensions}.
    """
    results = []

    logs = driver.get_log("performance")
    for entry in logs:
        try:
            log = json.loads(entry["message"])["message"]

            if log["method"] == "Network.responseReceived":
                request_id = log["params"]["requestId"]
                response = log["params"]["response"]
                url = response["url"]

                # Use Content-Type from headers
                headers = {k.lower(): v for k, v in response.get("headers", {}).items()}
                content_type = headers.get("content-type", "")

                print(f"\n[{request_id}] URL: {url}")
                print(f"  content-type={content_type}")

                if "json" not in content_type:
                    continue

                try:
                    body_dict = driver.execute_cdp_cmd(
                        "Network.getResponseBody", {"requestId": request_id}
                    )
                except Exception as e:
                    print(f"[{request_id}] Failed to fetch body: {e}")
                    continue

                body = body_dict.get("body")
                if not body:
                    print(f"[{request_id}] Empty body")
                    continue

                try:
                    data = json.loads(body)
                except Exception as e:
                    print(f"[{request_id}] JSON decode failed: {e}")
                    continue

                if isinstance(data, dict) and "data" in data:
                    # Get first 2 keys inside data
                    data_keys = list(data["data"].keys())[:2]
                    print(f"[{request_id}] Found data keys: {data_keys}")

                    results.append({
                        "requestId": request_id,
                        "url": url,
                        "data": data["data"],
                        "data_keys": data_keys,
                        "status": data.get("status"),
                        "extensions": data.get("extensions"),
                    })
                else:
                    print(f"[{request_id}] No 'data' key found")

        except Exception as e:
            print(f"Error processing entry: {e}")
            continue

    return results



def list_logged_urls(driver, limit: int = 5000):
    """
    List all logged network response URLs from performance logs.
    Helps debug whether /graphql/query requests are captured.
    """
    logs = driver.get_log("performance")
    urls = []

    print(f"\n--- Listing up to {limit} network responses ---")
    for entry in logs:
        try:
            log = json.loads(entry["message"])["message"]
            if log["method"] == "Network.responseReceived":
                response = log["params"]["response"]
                url = response["url"]
                urls.append([url,response])
        except Exception:
            continue
    graphql_urls = [[u,r] for u,r in urls if '/graphql/query' in u]
    # Print unique URLs (limited for readability)
    # unique_urls = list(dict.fromkeys(urls))  # preserve order, remove dups
    # for idx, url in enumerate(unique_urls[:limit], 1):
    #     print(f"{idx}. {url}")

    # print(f"\nTotal logged responses: {len(urls)}")
    # print(f"Unique URLs: {len(unique_urls)}")

    return urls,graphql_urls


def capture_instagram_requests(driver, limit: int = 5000):
    """
    Capture all instagram.com requests that include keywords: api, graphql, v1.
    Returns a list of dicts: {requestId, url, request, response}.
    """
    results = []
    keywords = ["api/v1", "graphql/query"]

    # Grab performance logs from Chrome
    logs = driver.get_log("performance")
    for entry in logs:
        try:
            msg = json.loads(entry["message"])["message"]
            method = msg.get("method", "")
            params = msg.get("params", {})

            # Collect request events
            if method == "Network.requestWillBeSent":
                url = params["request"]["url"]
                if "instagram.com/" in url and any(k in url for k in keywords):
                    results.append({
                        "requestId": params["requestId"],
                        "url": url,
                        "request": params["request"],
                        "response": None
                    })

            # Collect response events + body
            elif method == "Network.responseReceived":
                url = params["response"]["url"]
                if "instagram.com/" in url and any(k in url for k in keywords):
                    req_id = params["requestId"]
                    try:
                        body = driver.execute_cdp_cmd(
                            "Network.getResponseBody", {"requestId": req_id}
                        )
                        response_body = body.get("body", None)
                    except Exception as e:
                        response_body = f"Error fetching body: {e}"

                    results.append({
                        "requestId": req_id,
                        "url": url,
                        "request": None,
                        "response": response_body
                    })
        except Exception:
            continue

    # Merge requests + responses by requestId
    merged = {}
    for r in results:
        rid = r["requestId"]
        if rid not in merged:
            merged[rid] = {"requestId": rid, "url": r["url"], "request": None, "response": None}
        if r["request"]:
            merged[rid]["request"] = r["request"]
        if r["response"]:
            merged[rid]["response"] = r["response"]

    out = list(merged.values())

    # Optional: limit for readability
    return out[:limit]


import json

def extract_graphql_data_keys(captured_results):
    """
    Given the output of capture_instagram_requests, filter requests where
    URL matches 'graphql/query' or '/api/graphql', and return the keys 
    inside the 'data' object of the response.
    """
    patterns = ["graphql/query", "/api/graphql"]
    extracted = []

    for item in captured_results:
        url = item.get("url", "")
        response = item.get("response", None)

        # Only look at GraphQL endpoints
        if any(p in url for p in patterns) and response:
            try:
                # Parse response as JSON
                data = json.loads(response).get("data", {})
                if isinstance(data, dict):
                    extracted.append({
                        "requestId": item.get("requestId"),
                        "url": url,
                        "data_keys": list(data.keys())
                    })
            except Exception:
                # skip if response isn't JSON
                continue

    return extracted


# --- Parsing function ---

# def parse_graphql_responses(
#     extracted: List[Dict[str, Any]]
# ) -> List[Dict[str, Any]]:
#     """
#     Given output of extract_graphql_data_keys, parse GraphQL responses
#     into all matching registered models.
#     """
#     parsed_results = []
#     MODEL_REGISTRY: Dict[str, Type["BaseFlexibleSafeModel"]] = {}

#     for item in extracted:
#         url = item.get("url")
#         request_id = item.get("requestId")
#         data_keys = item.get("data_keys", [])
#         raw_response = item.get("response")

#         if not raw_response:
#             continue

#         try:
#             response_json = json.loads(raw_response)
#             data = response_json.get("data", {})
#         except Exception:
#             continue

#         models = []
#         for key in data_keys:
#             model_cls = MODEL_REGISTRY.get(key)
#             if model_cls:
#                 try:
#                     instance = model_cls.parse_obj(data)
#                     models.append({"key": key, "model": instance})
#                 except Exception as e:
#                     models.append({"key": key, "error": str(e)})

#         parsed_results.append({
#             "requestId": request_id,
#             "url": url,
#             "parsed_models": models,
#         })

#     return parsed_results

def load_flatten_schema(path: str) -> Dict[str, Dict[str, Any]]:
    with open(Path(path), "r") as f:
        config = yaml.safe_load(f)
    # Return a dict mapping patterns to settings
    return {entry["pattern"]: entry for entry in config["rules"].values()}

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Set, Union

def unique_keys_by_depth(
    obj: Any,
    *,
    max_depth: int | None = None,
    sample_list_items: int = 1,
) -> Dict[int, Set[str]]:
    """
    Walk `obj` and return a mapping depth -> set(keys) found at that depth.

    Behavior:
    - Depth 0 are the top-level keys if `obj` is a dict.
    - When a dict value is a list, we inspect only the first `sample_list_items`
      elements of that list (default 1) and traverse them (so lists don't multiply keys).
    - Non-dict, non-list values are not traversed further.
    - Stops if `max_depth` is reached (None => no limit).
    - Uses object id tracking to avoid infinite recursion for recursive structures.

    Returns:
        Dict[int, Set[str]]  (depth -> set of unique keys)
    """
    result: Dict[int, Set[str]] = defaultdict(set)
    seen_ids: Set[int] = set()

    def _recurse(o: Any, depth: int) -> None:
        if max_depth is not None and depth > max_depth:
            return
        oid = id(o)
        if oid in seen_ids:
            return
        # only track container objects to avoid huge seen set for primitives
        if isinstance(o, (dict, list)):
            seen_ids.add(oid)

        if isinstance(o, dict):
            # record keys at this depth
            for k in o.keys():
                result[depth].add(k)

            # traverse children: dict values -> depth+1
            for v in o.values():
                if isinstance(v, list):
                    # inspect only the first `sample_list_items` items
                    if len(v) == 0:
                        continue
                    for item in v[:max(1, sample_list_items)]:
                        _recurse(item, depth + 1)
                else:
                    _recurse(v, depth + 1)

        elif isinstance(o, list):
            # if a list appears where we expect keys (rare), inspect first elements
            if not o:
                return
            for item in o[:max(1, sample_list_items)]:
                _recurse(item, depth)

        else:
            # primitive: nothing to record
            return

    _recurse(obj, 0)
    return dict(result)

import json
from typing import Union, List, Dict, Any

def pretty_print_json(data: Union[Dict[str, Any], List[Dict[str, Any]]], 
                     indent: int = 2, 
                     sort_keys: bool = True,
                     ensure_ascii: bool = False) -> None:
    """
    Pretty print JSON data (single dict or list of dicts)
    
    Args:
        data: JSON data to print (dict or list of dicts)
        indent: Number of spaces for indentation
        sort_keys: Whether to sort dictionary keys
        ensure_ascii: Whether to escape non-ASCII characters
    """
    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        # Print list of dictionaries
        print("[")
        for i, item in enumerate(data):
            print(json.dumps(item, indent=indent, sort_keys=sort_keys, ensure_ascii=ensure_ascii), end="")
            if i < len(data) - 1:
                print(",")
            print()
        print("]")
    else:
        # Print single dictionary
        print(json.dumps(data, indent=indent, sort_keys=sort_keys, ensure_ascii=ensure_ascii))

# Alternative version that returns the string instead of printing
def pretty_json_str(data: Union[Dict[str, Any], List[Dict[str, Any]]], 
                   indent: int = 2, 
                   sort_keys: bool = True,
                   ensure_ascii: bool = False) -> str:
    """
    Return pretty formatted JSON string
    
    Args:
        data: JSON data to format (dict or list of dicts)
        indent: Number of spaces for indentation
        sort_keys: Whether to sort dictionary keys
        ensure_ascii: Whether to escape non-ASCII characters
        
    Returns:
        Formatted JSON string
    """
    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        result = "[\n"
        for i, item in enumerate(data):
            result += json.dumps(item, indent=indent, sort_keys=sort_keys, ensure_ascii=ensure_ascii)
            if i < len(data) - 1:
                result += ","
            result += "\n"
        result += "]"
        return result
    else:
        return json.dumps(data, indent=indent, sort_keys=sort_keys, ensure_ascii=ensure_ascii)

# Even simpler version using pprint
import pprint

def pretty_print_any(data: Any, width: int = 120, compact: bool = False) -> None:
    """
    Pretty print any Python data structure using pprint
    
    Args:
        data: Any Python data structure
        width: Maximum line width
        compact: Whether to use compact format
    """
    pp = pprint.PrettyPrinter(width=width, compact=compact,sort_dicts=True)
    pp.pprint(data)


def pretty_print_flattened(data: Union[Dict, List], max_sample: int = 5) -> None:
    """
    Specialized pretty printer for flattened data structures
    """
    if isinstance(data, dict) and 'rows_sample' in data:
        # Diagnostic output format
        print(f"Matched Rules: {data['matched_rules']}")
        print(f"Rows Count: {data['rows_count']}")
        print("Sample Rows:")
        pretty_print_json(data['rows_sample'][:max_sample])
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        # List of flattened rows
        print(f"Total Rows: {len(data)}")
        pretty_print_json(data[:max_sample])
    else:
        pretty_print_json(data)

# Usage with your data:
# pretty_print_flattened(diag)
# pretty_print_flattened(rows)


# Schema linter implementation and example run on the user's schema.
from typing import Any, Dict, List, Tuple, Union
import re, json, pprint

def schema_lint(schema: Dict[str, Any]) -> Dict[str, List[Dict[str, str]]]:
    """
    Lint a schema (the same structure used by apply_nested_schema).
    Returns a dict with lists of issues: errors, warnings, suggestions.
    Each issue is a dict: {"path": "...", "message": "...", "hint": "..."}
    Heuristics implemented:
      - invalid_regex: a schema key intended as regex (parent __strict__ = False or child __strict__ = False)
        but the pattern fails to compile.
      - ambiguous_container: a node with >1 child, no 'fields', and no '__separate__' -> likely needs __separate__.
      - explode_duplication: a child schema has 'unwrap' while the parent defines 'fields' -> parent fields
        will be replicated into exploded rows (maybe unintended).
      - separate_with_fields: parent has '__separate__'=True and also 'fields' -> warn (fields won't be merged into child rows).
      - list_keep_nested_without_fields: a child is a list-keeping node (no unwrap) that defines nested children but
        no fields - warn to confirm expected behavior.
    """
    errors = []
    warnings = []
    suggestions = []

    def _compile(pattern):
        try:
            re.compile(pattern)
            return True, None
        except re.error as e:
            return False, str(e)

    def walk(node: Dict[str, Any], path: str, parent_strict: bool = True):
        # node expected to be a dict (schema node)
        if not isinstance(node, dict):
            return

        # gather child keys (schema children)
        child_keys = [k for k in node.keys() if k not in ("fields", "__strict__", "unwrap", "__separate__")]

        # heuristic: ambiguous container
        if "fields" not in node and len(child_keys) > 1 and not node.get("__separate__", False):
            warnings.append({
                "path": path or "(root)",
                "message": "Container node with multiple child patterns but no 'fields' and no '__separate__'.",
                "hint": "If child patterns represent distinct row families, add '__separate__: True' to avoid merging their keys."
            })

        # warn when __separate__ used with fields: user might expect merging; explain behavior
        if node.get("__separate__", False) and "fields" in node:
            warnings.append({
                "path": path or "(root)",
                "message": "__separate__ is True but this node also defines 'fields'.",
                "hint": "Fields at this level will NOT be merged into child rows when '__separate__' is True. Remove '__separate__' if you intended merging."
            })

        # for each child key, check regex validity when strict is False (parent or child)
        for sk, scfg in node.items():
            if sk in ("fields", "__strict__", "unwrap", "__separate__"):
                continue
            # determine effective strictness for this child
            child_strict = (scfg.get("__strict__", node.get("__strict__", True)) if isinstance(scfg, dict) else node.get("__strict__", True))

            if not child_strict:
                ok, err = _compile(sk)
                if not ok:
                    errors.append({
                        "path": f"{path}.{sk}" if path else sk,
                        "message": f"Invalid regex pattern: {err}",
                        "hint": "Fix the regex or set child __strict__=True for exact match."
                    })

            # explode duplication: parent has fields and child has unwrap -> parent fields will be duplicated across exploded rows
            if "unwrap" in (scfg if isinstance(scfg, dict) else {}) and "fields" in node:
                warnings.append({
                    "path": f"{path}.{sk}" if path else sk,
                    "message": "Child has 'unwrap' while parent defines 'fields'.",
                    "hint": "Parent-level fields will be duplicated into each exploded child row. If that's unintended, remove parent fields or avoid unwrap."
                })

            # list-keeping nested children without fields - tricky case
            # If child schema has nested children (non-empty) but no 'unwrap' (so lists are kept), warn user to confirm.
            if isinstance(scfg, dict):
                nested_children = [k for k in scfg.keys() if k not in ("fields", "__strict__", "unwrap", "__separate__")]
                if nested_children and "unwrap" not in scfg and "fields" not in scfg:
                    warnings.append({
                        "path": f"{path}.{sk}" if path else sk,
                        "message": "Node keeps lists intact (no 'unwrap') and defines nested children but has no 'fields'.",
                        "hint": "Each list item will be processed for nested children. Confirm you intended to keep the list as a single field rather than explode."
                    })

            # Recurse into child schema
            if isinstance(scfg, dict):
                walk(scfg, f"{path}.{sk}" if path else sk, parent_strict=node.get("__strict__", True))

    walk(schema, "", True)
    return {"errors": errors, "warnings": warnings, "suggestions": suggestions}


# # Example: run linter on the user's schema from their last message
# user_schema = {
#   "data": {
#     "__strict__": True,
#     "__separate__": True,
#     "xdt_api__v1__feed__user_timeline_graphql_connection": {
#       "edges": {
#         "unwrap": "node",
#         "fields": ["id", "pk", "code", "taken_at", "comment_count", "like_count"],
#         "image_versions2": {
#           "candidates": {
#             "fields": ["url", "height", "width"]
#           }
#         },
#         "user": {
#           "fields": ["id", "username"]
#         }
#       }
#     },
#     "xdt_api__v1__media__media_id__comments__connection": {
#       "unwrap": "edges",
#       "node": {
#         "fields": ["pk","child_comment_count", "text", "giphy_media_info", "created_at", "parent_comment_id", "comment_like_count"],
#         "user": {
#           "fields": ["id", "username"]
#         }
#       }
#     },
#     "fetch__XDTMediaDict": {
#       "fields": ["code", "pk", "id", "taken_at", "media_type", "product_type"],
#       "carousel_media": {
#         "fields": ["id"],
#         "image_versions2": {
#           "candidates": {
#             "fields": ["url", "height", "width"]
#           }
#         }
#       },
#       "image_versions2": {
#         "candidates": {
#           "fields": ["url", "height", "width"]
#         }
#       },
#       "user": {
#         "fields": ["id", "username"]
#       }
#     }
#   },
#   "extensions": {
#     "__strict__": False,
#     "unwrap": "all_video_dash_prefetch_representations",
#     "fields": ["video_id"],
#     "representations": {
#       "fields": ["base_url", "width", "height", "mime_type", "representation_id"],
#       "segments": {
#         "fields": ["start", "end"]
#       }
#     }
#   }
# }

# lint_result = schema_lint(user_schema)
# print("Linter results:")
# pprint.pprint(lint_result)


from typing import Optional, Tuple, List, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

def click_all_reply_buttons_gently_bk(
    driver,
    container: Optional[WebElement | str] = None,
    container_selector: str = "div.html-div",
    candidate_selector: str = 'div[role="button"][tabindex="0"], a, button, span',
    match_pattern: re.Pattern = re.compile(
        r'\b(view (all|more)|view.*repl|show (all|more)|show replies|more replies)\b', re.I
    ),
    batch_scroll_steps: int = 4,
    step_scroll_pause: float = 0.12,
    delay_between_clicks: Tuple[float, float] = (0.12, 0.35),
    delay_after_batch: Tuple[float, float] = (0.4, 0.9),
    max_scroll_loops: int = 40,
    max_total_clicks: int = 300,
    wait_for_new_replies_timeout: float = 5.0,
    wait_for_new_replies_poll: float = 0.25,
) -> Tuple[int, List[str], Dict]:
    """
    Click all 'View all replies' buttons, scrolling gently and waiting for new replies to load.

    Returns:
        (clicked_count, clicked_texts, diagnostics)
    """
    def _log(msg, level="info"):
        try:
            getattr(logger, level)(msg)
        except Exception:
            print(f"[{level.upper()}] {msg}")

    # Resolve container element
    if container is None:
        try:
            elem = driver.execute_script("return document.documentElement;")
        except Exception:
            elem = driver.find_element(By.TAG_NAME, "html")
    elif isinstance(container, str):
        try:
            elem = driver.find_element(By.CSS_SELECTOR, container)
        except Exception:
            elem = driver.find_element(By.TAG_NAME, "html")
    else:
        elem = container

    # --- helpers ---
    def get_comment_count() -> int:
        try:
            return int(driver.execute_script("return document.querySelectorAll('div.html-div').length;") or 0)
        except Exception:
            return 0

    def collect_buttons() -> List[WebElement]:
        """Return list of unclicked, visible reply buttons."""
        try:
            candidates = elem.find_elements(By.CSS_SELECTOR, candidate_selector)
        except Exception:
            candidates = driver.find_elements(By.CSS_SELECTOR, candidate_selector)

        filtered = []
        for c in candidates:
            try:
                if not c.is_displayed():
                    continue
                txt = (c.text or "").strip()
                if not txt:
                    continue
                if match_pattern.search(txt) and c.get_attribute("data-replies-clicked") != "1":
                    filtered.append(c)
            except Exception:
                continue  # skip stale or detached nodes
        return filtered

    def scroll_container(delta: int):
        try:
            driver.execute_script("arguments[0].scrollBy(0, arguments[1]);", elem, delta)
        except Exception:
            driver.execute_script("window.scrollBy(0, arguments[0]);", delta)

    # --- main state ---
    diagnostics = {"clicks": []}
    clicked_texts: List[str] = []
    clicked_count = 0
    prev_comment_count = get_comment_count()

    _log(f"Starting reply-clicker (initial comments={prev_comment_count})")

    for loop in range(max_scroll_loops):
        candidates = collect_buttons()
        if not candidates:
            _log(f"No unclicked buttons found in loop {loop+1}, scrolling gently...", "debug")
        else:
            _log(f"Loop {loop+1}: found {len(candidates)} candidate buttons", "debug")

        processed_this_pass = 0

        for btn in candidates:
            if clicked_count >= max_total_clicks:
                _log("Reached max_total_clicks, stopping", "warn")
                diagnostics["summary"] = {"clicked_total": clicked_count, "loops": loop + 1}
                return clicked_count, clicked_texts, diagnostics

            try:
                # skip stale buttons right away
                if not btn.is_displayed():
                    continue

                # Scroll into view
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                except Exception:
                    pass
                time.sleep(random.uniform(*delay_between_clicks))

                # Click attempt
                clicked_ok = False
                try:
                    btn.click()
                    clicked_ok = True
                except Exception:
                    try:
                        driver.execute_script("arguments[0].click();", btn)
                        clicked_ok = True
                    except Exception:
                        clicked_ok = False

                if not clicked_ok:
                    _log("Click failed; element may be stale or detached", "debug")
                    continue

                # Mark as clicked safely
                try:
                    driver.execute_script(
                        "if(arguments[0].isConnected){arguments[0].setAttribute('data-replies-clicked','1');}",
                        btn,
                    )
                except Exception:
                    pass  # ignore stale reference

                text = (btn.text or "").strip()
                clicked_texts.append(text)
                clicked_count += 1
                processed_this_pass += 1

                # Wait for new replies to load
                old_count = prev_comment_count
                new_count = old_count
                waited = 0.0
                while waited < wait_for_new_replies_timeout:
                    time.sleep(wait_for_new_replies_poll)
                    waited += wait_for_new_replies_poll
                    try:
                        new_count = get_comment_count()
                    except Exception:
                        continue
                    if new_count > old_count:
                        _log(f"New replies detected ({old_count}→{new_count}) after click '{text[:30]}...'", "debug")
                        prev_comment_count = new_count
                        break
                else:
                    _log(f"No new replies after clicking '{text[:30]}...' within {wait_for_new_replies_timeout}s", "debug")

                diagnostics["clicks"].append({
                    "text": text,
                    "comments_before": old_count,
                    "comments_after": new_count,
                    "waited_sec": round(waited, 2),
                    "new_replies": max(0, new_count - old_count),
                })

                time.sleep(random.uniform(*delay_between_clicks))

            except Exception as e:
                if "stale" in str(e).lower():
                    continue
                _log(f"Error while processing a button: {e}", "debug")
                continue

        # If nothing processed this pass, we may need to scroll further
        if processed_this_pass == 0:
            _log("No new valid clicks this pass — gentle scroll to load more.", "debug")

        # Gentle scroll batch
        for _ in range(batch_scroll_steps):
            try:
                delta = int(driver.execute_script("return (arguments[0].clientHeight||window.innerHeight)*0.3;", elem))
            except Exception:
                delta = 400
            scroll_container(delta)
            time.sleep(step_scroll_pause * random.uniform(0.8, 1.6))

        time.sleep(random.uniform(*delay_after_batch))

        # Stop if no new comments and no buttons remain
        current_count = get_comment_count()
        if current_count <= prev_comment_count and not collect_buttons():
            _log("No new comments or buttons found; stopping", "debug")
            break
        prev_comment_count = current_count

    _log(f"Finished clicking replies: {clicked_count} total")
    diagnostics["summary"] = {"clicked_total": clicked_count, "loops": loop + 1}
    return clicked_count, clicked_texts, diagnostics


import time, random, re, math
from selenium.webdriver.common.action_chains import ActionChains

def click_all_reply_buttons_gently(
    driver,
    container: Optional[WebElement | str] = None,
    container_selector: str = "div.html-div",
    candidate_selector: str = 'div[role="button"][tabindex="0"], a, button, span',
    match_pattern: re.Pattern = re.compile(
        r'\b(view (all|more)|view.*repl|show (all|more)|show replies|more replies)\b', re.I
    ),
    batch_scroll_steps: int = 4,
    step_scroll_pause: float = 0.12,
    delay_between_clicks: Tuple[float, float] = (0.3, 0.9),
    delay_after_batch: Tuple[float, float] = (0.6, 1.2),
    max_scroll_loops: int = 20,
    max_total_clicks: int = 10,
    wait_for_new_replies_timeout: float = 5.0,
    wait_for_new_replies_poll: float = 0.25,
) -> Tuple[int, List[str], Dict]:
    """
    Click all 'View all replies' buttons in a human-like way — 
    scrolling softly, moving cursor gradually, clicking with delays.

    Returns:
        (clicked_count, clicked_texts, diagnostics)
    """

    def _log(msg, level="info"):
        try:
            getattr(logger, level)(msg)
        except Exception:
            print(f"[{level.upper()}] {msg}")

    # --- helpers for human-like motion ---
    def random_human_pause(base=(0.4, 1.3), long_pause_chance=0.15):
        delay = random.uniform(*base) * random.uniform(0.8, 1.5)
        if random.random() < long_pause_chance:
            delay *= random.uniform(1.8, 3.5)
        time.sleep(delay)

    def human_like_scroll(driver, target, container_selector: str | None = None, settle_timeout: float = 3.0):
        """
        Gently scrolls the target element into view within a specific scrollable container,
        ensuring it doesn't overshoot when new comments dynamically load.
        """
        try:
            if container_selector:
                container = driver.find_element(By.CSS_SELECTOR, container_selector)
            else:
                container = driver.execute_script("return document.scrollingElement || document.documentElement;")

            driver.execute_script("""
                const container = arguments[0];
                const target = arguments[1];
                if (!container || !target) return;

                // Clamp scroll target so we never overshoot the container
                const cRect = container.getBoundingClientRect();
                const tRect = target.getBoundingClientRect();
                const targetCenter = tRect.top - cRect.top - (cRect.height / 2);

                const newScroll = container.scrollTop + (targetCenter * 0.5);
                const maxScroll = container.scrollHeight - container.clientHeight;
                container.scrollTop = Math.max(0, Math.min(maxScroll, newScroll));
            """, container, target)

            # Wait for content to "settle" — DOM expansions can shift positions
            stable_time = 0.0
            last_height = driver.execute_script("return arguments[0].scrollHeight;", container)
            while stable_time < settle_timeout:
                time.sleep(0.2)
                new_height = driver.execute_script("return arguments[0].scrollHeight;", container)
                if abs(new_height - last_height) < 10:  # no major content change
                    stable_time += 0.2
                else:
                    stable_time = 0.0  # reset timer if height keeps changing
                    last_height = new_height

        except Exception as e:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", target)
            except Exception:
                pass

        # Gentle pause so the scroll feels human and ensures full render
        time.sleep(random.uniform(0.5, 1.2))

    def human_like_move_and_click(driver, element, container_selector: str | None = None):
        """
        Moves the mouse cursor toward the element inside the given container,
        simulating human-like motion, then clicks.
        """
        try:
            # Get container bounds for offset calculation
            if container_selector:
                container = driver.find_element(By.CSS_SELECTOR, container_selector)
                c_rect = driver.execute_script("""
                    const r = arguments[0].getBoundingClientRect();
                    return {left: r.left, top: r.top};
                """, container)
                container_offset_x = c_rect.get("left", 0)
                container_offset_y = c_rect.get("top", 0)
            else:
                container_offset_x = 0
                container_offset_y = 0

            actions = ActionChains(driver)
            size = element.size

            # Random offsets within element bounds
            offset_x = size["width"] * random.uniform(0.3, 0.7)
            offset_y = size["height"] * random.uniform(0.3, 0.7)

            # Move cursor within the container space
            actions.move_to_element_with_offset(element, offset_x, offset_y)
            # actions.move_to_element_with_offset(
            #     element,
            #     offset_x - container_offset_x,
            #     offset_y - container_offset_y
            # )
            actions.pause(random.uniform(0.3, 0.8))
            actions.click()
            actions.perform()

        except Exception:
            driver.execute_script("arguments[0].click();", element)


    # --- container resolution ---
    if container is None:
        try:
            elem = driver.execute_script("return document.documentElement;")
        except Exception:
            elem = driver.find_element(By.TAG_NAME, "html")
    elif isinstance(container, str):
        try:
            elem = driver.find_element(By.CSS_SELECTOR, container)
        except Exception:
            elem = driver.find_element(By.TAG_NAME, "html")
    else:
        elem = container

    # --- sub-helpers ---
    def get_comment_count() -> int:
        try:
            return int(driver.execute_script("return document.querySelectorAll('div.html-div').length;") or 0)
        except Exception:
            return 0

    def collect_buttons() -> List[WebElement]:
        try:
            candidates = elem.find_elements(By.CSS_SELECTOR, candidate_selector)
        except Exception:
            candidates = driver.find_elements(By.CSS_SELECTOR, candidate_selector)

        filtered = []
        for c in candidates:
            try:
                if not c.is_displayed():
                    continue
                txt = (c.text or "").strip()
                if not txt:
                    continue
                if match_pattern.search(txt) and c.get_attribute("data-replies-clicked") != "1":
                    filtered.append(c)
            except Exception:
                continue
        return filtered

    def scroll_container(delta: int):
        try:
            driver.execute_script("arguments[0].scrollBy(0, arguments[1]);", elem, delta)
        except Exception:
            driver.execute_script("window.scrollBy(0, arguments[0]);", delta)

    # --- main state ---
    diagnostics = {"clicks": []}
    clicked_texts: List[str] = []
    clicked_count = 0
    prev_comment_count = get_comment_count()

    _log(f"Starting human-like reply clicker (initial comments={prev_comment_count})")

    for loop in range(max_scroll_loops):
        candidates = collect_buttons()
        if not candidates:
            _log(f"No unclicked buttons found in loop {loop+1}, scrolling gently...", "debug")
        else:
            _log(f"Loop {loop+1}: found {len(candidates)} candidate buttons", "debug")

        processed_this_pass = 0

        for btn in candidates:
            if clicked_count >= max_total_clicks:
                _log("Reached max_total_clicks, stopping", "warn")
                diagnostics["summary"] = {"clicked_total": clicked_count, "loops": loop + 1}
                return clicked_count, clicked_texts, diagnostics

            try:
                if not btn.is_displayed():
                    continue

                # Human-like scroll and pause
                human_like_scroll(driver, btn, container_selector=container_selector)
                random_human_pause((0.2, 1.0))

                # Click attempt
                human_like_move_and_click(driver, btn, container_selector=container_selector)
                random_human_pause((0.2, 0.8))

                # Mark as clicked
                try:
                    driver.execute_script(
                        "if(arguments[0].isConnected){arguments[0].setAttribute('data-replies-clicked','1');}",
                        btn,
                    )
                except Exception:
                    pass

                text = (btn.text or "").strip()
                clicked_texts.append(text)
                clicked_count += 1
                processed_this_pass += 1

                # Wait for replies to appear
                old_count = prev_comment_count
                new_count = old_count
                waited = 0.0
                while waited < wait_for_new_replies_timeout:
                    time.sleep(wait_for_new_replies_poll)
                    waited += wait_for_new_replies_poll
                    try:
                        new_count = get_comment_count()
                    except Exception:
                        continue
                    if new_count > old_count:
                        _log(f"New replies detected ({old_count}→{new_count}) after click '{text[:30]}...'", "debug")
                        prev_comment_count = new_count
                        break
                else:
                    _log(f"No new replies after clicking '{text[:30]}...' within {wait_for_new_replies_timeout}s", "debug")

                diagnostics["clicks"].append({
                    "text": text,
                    "comments_before": old_count,
                    "comments_after": new_count,
                    "waited_sec": round(waited, 2),
                    "new_replies": max(0, new_count - old_count),
                })

                # Occasionally simulate “reading” pause
                if random.random() < 0.12:
                    random_human_pause((1.5, 3.5))

            except Exception as e:
                if "stale" in str(e).lower():
                    continue
                _log(f"Error while processing a button: {e}", "debug")
                continue

        # Gentle scroll batch
        for _ in range(batch_scroll_steps):
            try:
                delta = int(driver.execute_script("return (arguments[0].clientHeight||window.innerHeight)*0.3;", elem))
            except Exception:
                delta = 400
            scroll_container(delta)
            time.sleep(step_scroll_pause * random.uniform(0.8, 1.6))

        random_human_pause(delay_after_batch)

        # Stop if no new comments or buttons remain
        current_count = get_comment_count()
        if current_count <= prev_comment_count and not collect_buttons():
            _log("No new comments or buttons found; stopping", "debug")
            break
        prev_comment_count = current_count

    _log(f"Finished clicking replies: {clicked_count} total")
    diagnostics["summary"] = {"clicked_total": clicked_count, "loops": loop + 1}
    return clicked_count, clicked_texts, diagnostics



import json

def extract_script_embedded_comments(driver, sep="$$", logging=False):
    """
    Extracts Instagram post comments (main + replies) from the current page.

    Args:
        driver: Selenium WebDriver instance (already on an Instagram post page)
        sep (str): Separator for flattened keys
        logging (bool): Enable or disable browser console logs

    Returns:
        dict: { comments: [...], count: int, timestamp: str, error?: str }
    """
    js_script = f"""
    const done = arguments[0];

    async function extractInstagramComments(options = {{}}) {{
      const {{
        sep = "{sep}",
        logging = {str(logging).lower()}
      }} = options;

      const log = (...args) => {{ if (logging) console.log("[IG Comment Extractor]", ...args); }};

      function flattenObject(obj, prefix = "") {{
        const res = {{}};
        for (const [k, v] of Object.entries(obj)) {{
          const newKey = prefix ? `${{prefix}}${{sep}}${{k}}` : k;
          if (v && typeof v === "object" && !Array.isArray(v)) {{
            Object.assign(res, flattenObject(v, newKey));
          }} else if (Array.isArray(v)) {{
            v.forEach((item) => {{
              if (item && typeof item === "object") {{
                Object.assign(res, flattenObject(item, newKey));
              }} else {{
                res[newKey] = item;
              }}
            }});
          }} else {{
            res[newKey] = v;
          }}
        }}
        return res;
      }}

      function deepFind(obj, targetKey) {{
        if (!obj || typeof obj !== "object") return null;
        if (Object.prototype.hasOwnProperty.call(obj, targetKey)) return obj[targetKey];
        for (const v of Object.values(obj)) {{
          if (v && typeof v === "object") {{
            const res = deepFind(v, targetKey);
            if (res) return res;
          }}
        }}
        return null;
      }}

      const scripts = Array.from(document.querySelectorAll("script"));
      const keysToSearch = [
        "xdt_api__v1__media__media_id__comments__connection",
        "xdt_api__v1__media__media_id__comments__parent_comment_id__child_comments__connection"
      ];

      const allComments = [];

      for (const [i, s] of scripts.entries()) {{
        const text = s.textContent || "";
        if (!text.includes("xdt_api__v1__media__media_id__comments__")) continue;

        try {{
          const start = text.indexOf("{{");
          const end = text.lastIndexOf("}}");
          const json = JSON.parse(text.slice(start, end + 1));

          for (const key of keysToSearch) {{
            const data = deepFind(json, key);
            if (data && Array.isArray(data.edges)) {{
              for (const edge of data.edges) {{
                if (!edge.node) continue;
                const baseKey = `data${{sep}}${{key}}${{sep}}edges`;
                const flat = flattenObject(edge.node, baseKey);
                flat["type"] = key.includes("child_comments") ? "reply" : "main";
                allComments.push(flat);
              }}
            }}
          }}
        }} catch (err) {{
          log(`Skipping script[${{i}}] - JSON parse failed: ${{err.message}}`);
        }}
      }}

      if (!allComments.length) {{
        return done({{ error: "No comment data found.", comments: [], count: 0 }});
      }}

      return done({{
        comments: allComments,
        count: allComments.length,
        timestamp: new Date().toISOString()
      }});
    }}

    extractInstagramComments({{ sep: "{sep}", logging: {str(logging).lower()} }});
    """

    # Execute JS inside the browser context
    try:
        result = driver.execute_async_script(js_script)
        result['current_url'] = driver.current_url
        result['flattened_data'] = result.pop('comments',[])
        return result
    except Exception as e:
        return {"error": str(e), "flattened_data": [], "count": 0, "current_url": driver.current_url}

    return result
