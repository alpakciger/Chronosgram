import json
import re
import matplotlib.pyplot as plt
import pandas as pd
import requests
from bs4 import BeautifulSoup


def sanitize_channel_input(raw_input: str) -> str:
    """Cleans Telegram channel input from URLs, @ symbols, and invalid characters."""
    text = raw_input.strip()
    if "t.me/" in text:
        text = text.split("t.me/")[-1].replace("s/", "").strip("/")
    return re.sub(r"[^a-zA-Z0-9_]", "", text)


def scrape_public_telegram_channel(
    channel_name: str, max_messages: int = 150
) -> list:
    """Scrapes messages and metadata from a public Telegram channel preview."""
    channel_name = sanitize_channel_input(channel_name)
    if not channel_name:
        print("[-] Invalid channel handle.")
        return []

    base_url = f"https://t.me/s/{channel_name}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    collected_data = []
    current_url = base_url
    print(f"\n[*] Targeting Public Telegram Channel: @{channel_name}")

    while len(collected_data) < max_messages:
        response = requests.get(current_url, headers=headers)
        if response.status_code != 200:
            print(
                f"[-] Failed to fetch data. HTTP Status: {response.status_code}"
            )
            break

        soup = BeautifulSoup(response.text, "html.parser")
        messages = soup.find_all("div", class_="tgme_widget_message")

        if not messages:
            print(
                f"[!] No messages found or target channel '@{channel_name}'"
                " does not exist."
            )
            break

        for msg in messages:
            msg_id = msg.get("data-post")
            text_div = msg.find("div", class_="tgme_widget_message_text")
            content = text_div.get_text(separator=" ", strip=True) if text_div else ""

            time_tag = msg.find("time", class_="time")
            datetime_str = (
                time_tag.get("datetime")
                if time_tag and time_tag.has_attr("datetime")
                else None
            )

            views_span = msg.find("span", class_="tgme_widget_message_views")
            views = views_span.get_text(strip=True) if views_span else "0"

            links = [
                a.get("href")
                for a in (text_div.find_all("a") if text_div else [])
                if a.get("href")
            ]

            collected_data.append({
                "message_id": msg_id,
                "timestamp": datetime_str,
                "content": content,
                "views": views,
                "outlinks": links,
            })

            if len(collected_data) >= max_messages:
                break

        prev_link = soup.find("link", rel="prev")
        if prev_link and prev_link.get("href"):
            current_url = f"https://t.me{prev_link.get('href')}"
        else:
            break

        print(
            f"[+] Extracted batch. Total messages collected:"
            f" {len(collected_data)}"
        )

    return collected_data


def process_and_save_data(
    data: list, filename: str
) -> pd.DataFrame:
    """Cleans, sorts, saves dataset to JSON, and prepares DataFrame for analysis."""
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values(
        by="timestamp", ascending=True
    )

    # Save to JSON
    df_to_save = df.copy()
    df_to_save["timestamp"] = df_to_save["timestamp"].dt.strftime(
        "%Y-%m-%dT%H:%M:%S%z"
    )
    sorted_records = df_to_save.to_dict(orient="records")

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(sorted_records, f, ensure_ascii=False, indent=4)
    print(
        f"[✓] Saved {len(sorted_records)} chronologically sorted items to"
        f" '{filename}'"
    )

    # Feature engineering for analyzer
    df["hour"] = df["timestamp"].dt.hour
    df["day_name"] = df["timestamp"].dt.day_name()
    df["date"] = df["timestamp"].dt.date
    return df


def display_activity_summary(df: pd.DataFrame, channel_name: str):
    """Outputs behavioral patterns and peak activity times to terminal."""
    print("\n" + "=" * 60)
    print(f" [*] OSINT BEHAVIORAL REPORT: @{channel_name}")
    print("=" * 60)
    print(f"[+] Total Analyzed Messages : {len(df)}")
    print(f"[+] Timeframe Range         : {df['date'].min()} to {df['date'].max()}")

    top_hours = df["hour"].value_counts().head(3)
    print("\n[+] Peak Operational Hours (UTC):")
    for hour, count in top_hours.items():
        print(f"    - {hour:02d}:00 UTC -> {count} posts")

    total_links = df["outlinks"].apply(len).sum()
    print(f"\n[+] Total External URLs Extracted: {total_links}")
    print("=" * 60)


def generate_visual_report(df: pd.DataFrame, output_image: str):
    """Generates dual dark-themed charts for hourly and daily activity."""
    plt.style.use("dark_background")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Hourly Distribution
    hourly_counts = (
        df["hour"].value_counts().reindex(range(24), fill_value=0).sort_index()
    )
    ax1.bar(
        hourly_counts.index,
        hourly_counts.values,
        color="#00ADB5",
        edgecolor="#393E46",
        alpha=0.85,
    )
    ax1.set_title("Hourly Activity Distribution (UTC)", fontsize=12, pad=10)
    ax1.set_xlabel("Hour of Day (00:00 - 23:00 UTC)", fontsize=10)
    ax1.set_ylabel("Message Count", fontsize=10)
    ax1.set_xticks(range(0, 24, 2))
    ax1.grid(axis="y", linestyle="--", alpha=0.3)

    # Weekly Distribution
    days_order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    daily_counts = (
        df["day_name"].value_counts().reindex(days_order, fill_value=0)
    )
    ax2.bar(
        daily_counts.index,
        daily_counts.values,
        color="#FF5722",
        edgecolor="#393E46",
        alpha=0.85,
    )
    ax2.set_title("Weekly Activity Distribution", fontsize=12, pad=10)
    ax2.set_xlabel("Day of the Week", fontsize=10)
    ax2.set_ylabel("Message Count", fontsize=10)
    ax2.tick_params(axis="x", rotation=30)
    ax2.grid(axis="y", linestyle="--", alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_image, dpi=300)
    print(f"[✓] Visual intelligence report saved as '{output_image}'\n")
    plt.close()


if __name__ == "__main__":
    target_input = input(
        "[?] Enter target Telegram channel (username or link): "
    ).strip()

    if target_input:
        cleaned_handle = sanitize_channel_input(target_input)
        extracted_posts = scrape_public_telegram_channel(
            cleaned_handle, max_messages=100
        )

        if extracted_posts:
            json_file = f"telegram_{cleaned_handle}.json"
            report_img = f"report_telegram_{cleaned_handle}.png"

            df = process_and_save_data(extracted_posts, filename=json_file)
            if not df.empty:
                display_activity_summary(df, channel_name=cleaned_handle)
                generate_visual_report(df, output_image=report_img)
    else:
        print("[-] Target channel cannot be empty.")