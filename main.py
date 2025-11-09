"""Instagram Scraper - Main Entry Point"""
import asyncio, logging, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scraper import InstagramScraper
from config import load_config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def main():
    examples = {
        "1": {"name": "NASA profile", "input": {"username": "nasa", "scrape_type": "profile"}},
        "2": {"name": "NASA posts", "input": {"username": "nasa", "scrape_type": "posts", "max_posts": 20}},
        "3": {"name": "Custom username", "input": {"username": "natgeo", "scrape_type": "profile"}},
    }

    print("\n" + "="*60 + "\nInstagram Scraper\n" + "="*60)
    print("\n⚠️  IMPORTANT: Requires residential proxies + login session for full access")
    print("\nSelect an example:"), [print(f"  {k}. {v['name']}") for k, v in examples.items()]

    choice = input("\nChoice (1-3): ").strip()
    input_data = examples.get(choice, examples["1"])["input"]

    config = load_config()
    scraper = InstagramScraper(proxy_config=config['proxy'], rate_limit=config['rate_limit'],
                               cache_config=config['cache'], output_dir=config['output_dir'])

    try:
        results = await scraper.run(input_data, export_formats=['json'])
        print(f"\n✓ Scraped {len(results)} items")
        if results and 'username' in results[0]:
            profile = results[0]
            print(f"\nProfile: @{profile['username']}")
            print(f"  Followers: {profile['follower_count']:,}")
            print(f"  Posts: {profile['post_count']:,}")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Configure residential proxies in .env")
        print("  2. Add login_session cookies for private profiles")
        print("  3. Respect Instagram's rate limits (40 req/hour)")

if __name__ == "__main__":
    asyncio.run(main())
