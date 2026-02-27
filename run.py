import sys
import os
import asyncio
import argparse
from dotenv import load_dotenv

def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "update":
        load_dotenv()
        from updater import Updater
        asyncio.run(Updater(
            http_proxy=os.getenv("UPDATE_HTTP_PROXY", ""),
            https_proxy=os.getenv("UPDATE_HTTPS_PROXY", ""),
        ).manual_update())
        sys.exit(0)
    parser = argparse.ArgumentParser(description="GhostPayments — Crypto Payment Processor")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    parser.add_argument("--generate-token", action="store_true", help="Print a new nanoid(20) token to stdout and exit")
    args = parser.parse_args()
    if args.version:
        from updater import Updater
        print(Updater().current_version)
        sys.exit(0)
    if args.generate_token:
        from nanoid import generate
        print(generate(size=20))
        sys.exit(0)
    load_dotenv()
    from app.db import init_db
    init_db()
    from app import create_app
    app = create_app()
    auto_update = os.getenv("AUTO_UPDATE", "true").lower() == "true"
    if auto_update:
        import threading
        from updater import Updater
        shutdown_event = asyncio.Event()
        updater = Updater(
            check_interval=int(os.getenv("UPDATE_CHECK_INTERVAL", 300)),
            check_on_startup=os.getenv("UPDATE_CHECK_ON_STARTUP", "true").lower() == "true",
            http_proxy=os.getenv("UPDATE_HTTP_PROXY", ""),
            https_proxy=os.getenv("UPDATE_HTTPS_PROXY", ""),
        )
        def _run_update_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(updater.update_loop(shutdown_event))
        threading.Thread(target=_run_update_loop, daemon=True).start()
    from waitress import serve
    serve(app, host="0.0.0.0", port=int(os.getenv("PORT", 5000)), threads=app.config["WAITRESS_THREADS"], channel_timeout=120)

if __name__ == "__main__":
    main()
