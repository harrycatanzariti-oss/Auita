"""Run with:  python -m aiuta          (the helper window)
           python -m aiuta setup    (only the family setup page)
           python -m aiuta try "open my email"   (test a phrase without a microphone)
"""
import sys


def main() -> None:
    args = sys.argv[1:]
    if args[:1] == ["setup"]:
        import time
        from .setup_server import SetupServer

        server = SetupServer()
        server.start()
        print("Setup page:", server.url)
        print("Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            server.stop()
    elif args[:1] == ["try"]:
        from . import actions, config
        from .brain import Brain

        brain = Brain(config.load(), runner=actions.Runner(dry_run="--real" not in args))
        said = " ".join(a for a in args[1:] if a != "--real")
        r = brain.hear(said)
        print(r.reply)
        if brain.runner.log:
            print("would run:" if brain.runner.dry_run else "ran:", brain.runner.log[-1])
    else:
        from .app import main as run_app

        run_app()


if __name__ == "__main__":
    main()
