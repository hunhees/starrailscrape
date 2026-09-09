"""
starrail_weekly_scrape.py
Reddit Scraper for r/HonkaiStarRail which scrapes 350 top weekly posts
using Selenium and BeautifulSoup
Author: Henry Nguyen
Date: 2026-06-05
Last Updated: 2026-08-27
"""

import datetime
import random
import sqlite3
import time
import tkinter as tk
from tkinter import messagebox
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By

def create_driver(cookie):
    """Creates Selenium driver and injects login cookie into old.reddit.com (old.reddit doesn't let you browse without logging in anymore)
    Args: 
        cookie: cookie login string
    Returns:
        Logged in selenium driver session
    
    """
    opts = Options()

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0"
    opts.set_preference("general.useragent.override", user_agent)
    opts.add_argument("--headless")

    driver = webdriver.Firefox(options=opts)

    driver.get("https://old.reddit.com/r/popular/")

    time.sleep(random.uniform(3,5))

    driver.add_cookie({
        "name": "reddit_session",
        "value": cookie,
        "domain": ".reddit.com"
    })

    time.sleep(random.uniform(2.5,5))
    driver.refresh()
    time.sleep(random.uniform(2,3))

    element  = driver.find_element(By.CSS_SELECTOR, ".no-visited")
    time.sleep(random.uniform(0.3,1))
    element.click()
    time.sleep(random.uniform(2,4))

    return driver


def get_links(subreddit):
    """Gets top weekly post links from first 14 pages of old.reddit
    Args:
        subreddit: subreddit you wish to browse
    Returns:
        list of top weekly links (350 total)
    """
    url = f'https://old.reddit.com/r/{subreddit}/top/?sort=top&t=week'
    
    opts = Options()
    opts.add_argument("--headless")
    opts.set_preference("permissions.default.image", 2)
    driver = create_driver()
    
    all_links = []

    # Loop 14 times for 14 pages
    for page in range(1, 15):
        print(f"Scraping links page {page} of 14...")
        driver.get(url)
        time.sleep(random.uniform(1, 3))
        driver.refresh()
        time.sleep(random.uniform(1, 3))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Filter out ads (t8_) so we only get real posts (t3_)
        posts = soup.find_all("div", class_="thing", attrs={"data-fullname": lambda x: x and x.startswith("t3_")})

        if not posts:
            print("No more posts found.")
            break

        for items in posts:
            title_tag = items.find("a", class_="bylink")
            if title_tag is None:
                continue

            href = title_tag.get("href")
            
            # Resolve relative URLs just in case
            if href.startswith("/"):
                href = f"https://old.reddit.com{href}"
                
            if href not in all_links:
                all_links.append(href)

        # Reddit next page
        next_button = soup.find("span", class_="nextprev")
        if next_button and next_button.find("a", rel="nofollow next"):
            url = next_button.find("a", rel="nofollow next").get("href")
        else:
            print("No next button found. Stopping pagination.")
            break

    driver.quit()
    print(f"Total links grabbed: {len(all_links)}")
    return all_links

### Scrape Main
def scrape_main_post(soup, url):
    """
    Scrapes reddit post data

    Args:
        soup: BeautifulSoup driver
        url: post url (string)

    Returns:
        dictionary containing url, scrape time, and the posts id, author, title, body, score, and number of comments 
    """
    # Get title text
    title = soup.find('a', class_='title')
    title_text = title.get_text() if title else None

    # Get post author
    post_author = soup.find('a', class_='author')
    post_author_text = post_author.get_text() if post_author else None

    # Get post body, upvotes
    post_body = soup.find('div', class_='usertext')
    post_body_text = post_body.get_text(strip=True) if post_body else None

    upvote = soup.find('div', class_='score')
    upvote_text = upvote.get_text() if upvote else None

    # Get post comment count
    comment_count = soup.find('a', class_='bylink')
    comment_count_text = comment_count.get_text() if comment_count else None

    # Date posted
    date_posted = soup.find('time')
    date_posted_text = date_posted.get_text() if date_posted else None

    # ID and scrape time
    try:
        post_id = url.split("/comments/")[1].split("/")[0]
    except (IndexError, AttributeError):
        post_id = "unknown"
        
    scrape_time = datetime.datetime.now().strftime('%d %b %Y')

    post_data = []
    post_data.append({
        'scrape_time': scrape_time,
        'url': url,
        'post_id': post_id,
        'date_posted': date_posted_text,
        'post_author': post_author_text,
        'post_title': title_text,
        'post_body': post_body_text,
        'post_score': upvote_text,
        'num_comments': comment_count_text,
    })
    return post_data


def scrape_post_comments(soup, url):
    """
    Scrape post comments

    Args:
        soup: BeautifulSoup driver
        url: post url
    Returns:
        dictionary containing comment id, score, body and the post id the comment was from

    """
    post_comments = soup.find_all("div", class_="thing", attrs={"data-type": "comment"})
    comment_data = []
    
    try:
        post_id = url.split("/comments/")[1].split("/")[0]
    except (IndexError, AttributeError):
        post_id = "unknown"

    for item in post_comments:
        # comment text
        comments = item.find('div', class_='usertext-body')
        comments_text = comments.get_text('\n', strip=True) if comments else None

        # id
        comment_id = item.get('data-fullname')
        
        # post score
        score = item.find('span', class_='score')
        score_text = score.text if score else None

        # list for export
        comment_data.append({
            "comment_id": comment_id,
            'comment_score': score_text,
            'comment_body': comments_text,
            'post_id': post_id
        })
    return comment_data

### Scrape
def scrape_data(all_links):
    """
    Scrapes post using scrape_main_post and scrape_post_comments. 
    Attempts to scrape, waits 30s if failed up to 3 times before skipping

    Args:
        all_links: list of links
    Returns:
        nested dictionary which contains all post and comment data from all_links
    """
    export_data = {'posts': []} 

    opts = Options()
    opts.add_argument("--headless")
    opts.set_preference("permissions.default.image", 2)
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
    opts.set_preference("general.useragent.override", user_agent)
    driver = create_driver()

    # Set over18 cookie to bypass NSFW warning
    driver.get("https://old.reddit.com")
    driver.add_cookie({"name": "over18", "value": "1", "domain": ".reddit.com"})

    for i, link in enumerate(all_links):
        url = link
        print(f"Scraping post {i+1} of {len(all_links)}...")

        try:
            # Initial page load
            driver.get(url)
            time.sleep(random.uniform(4, 10))
            
            success = False
            attempts = 0
            
            # Attempt loop if Reddit blocks
            while not success and attempts < 3:
                attempts += 1
                
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                main_post = scrape_main_post(soup, url)

                # Check if blocked
                if main_post[0]['post_title'] is None:
                    page_title = soup.title.string if soup.title else "Unknown"
                    if attempts < 3:
                        print(f"  [Attempt {attempts}] Blocked or empty (Page Title: '{page_title}'). Waiting 30s then refreshing...")
                        time.sleep(30)
                        driver.refresh()
                        time.sleep(random.uniform(4, 12)) # Short wait after refresh for DOM to load
                    else:
                        print(f"Failed to scrape post {i+1} after 3 attempts. Skipping...")
                else:
                    
                    post_comments = scrape_post_comments(soup, url)
                    post_bundle = {'post': main_post, 'comments': post_comments}
                    export_data['posts'].append(post_bundle)
                    success = True
                    
        except Exception as e:
            print(f"  Error on post {i+1}: {e}. Skipping...")
            continue
            
    driver.quit()
    return export_data

def insert_data(bundle, conn):
    """
    Inserts data into SQLite database
    
    Args:
        bundle: data bundle, nested dictionary from scrape_data
        conn: SQLite connection
    """
    cur = conn.cursor()
    
    for post in bundle['posts']:
        for item1 in post['post']:
            cur.execute("""INSERT OR IGNORE INTO posts (
                            url, date_posted, post_author, post_id, post_title, post_body, post_score, num_comments, created_at
                            ) VALUES (?,?,?,?,?,?,?,?,?)
                """, (item1['url'],  
                    item1['date_posted'], 
                    item1['post_author'],
                    item1['post_id'],
                    item1['post_title'],
                    item1['post_body'], 
                    item1['post_score'], 
                    item1['num_comments'],
                    item1['scrape_time']
            ))
            
    for comment in bundle['posts']:
        for item2 in comment['comments']:
            cur.execute("""INSERT OR IGNORE INTO comments(
                    comment_id, post_id, comment_body, comment_score
                    ) VALUES (?,?,?,?)
        """, (item2['comment_id'], item2['post_id'], item2['comment_body'], item2['comment_score']            
        ))


def main():
    all_links = get_links('HonkaiStarRail')
    export_data = scrape_data(all_links)

    file = 'starrail_weekly.db'
    conn = sqlite3.connect(file)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    # Most of this is just a check for 
    before_sum = count_entries(cur)
    insert_data(export_data, conn)
    after_sum = count_entries(cur)

    def check_input():
    user_text = entry.get()
    if user_text.upper() == 'Y':
        conn.commit()
        messagebox.showinfo(message="Database Committed Successfully!")
        root.destroy()
    elif user_text == "":
        messagebox.showwarning(message="Empty Field")
    else:
        messagebox.showerror(message="Error, Enter Y to commit")

    root = tk.Tk()
    root.title("HSR Scraper")
    root.geometry("300x150")

    a = tk.Label(root, text=f"Before: {before_sum}")
    a.pack()
    b = tk.Label(root, text=f"After: {after_sum}")
    b.pack()
    entry = tk.Entry(root)
    entry.pack(pady=10)

    btn = tk.Button(root, text="Submit (Y)", command=check_input)
    btn.pack(pady=5)

    root.mainloop()

if __name__ == "__main__"
    main()