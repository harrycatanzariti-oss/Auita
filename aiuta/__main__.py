"""Run with:  python -m aiuta                         (open Aiuta)
           python -m aiuta setup                   (open straight to the family setup page)
           python -m aiuta try "email Mary"        (test a phrase without a microphone)
           python -m aiuta try "email Mary" --real (and really open it)
"""
import sys


def main() -> None:
    args = sys.argv[1:]
    if args[:1] == ["try"]:
        from . import actions, config
        from .brain import Brain

        brain = Brain(config.load(), runner=actions.Runner(dry_run="--real" not in args))
        said = " ".join(a for a in args[1:] if a != "--real")
        print(brain.hear(said).reply)
        if brain.runner.log:
            print("would open:" if brain.runner.dry_run else "opened:", brain.runner.log[-1][1])
        return

    from .launcher import main as launch

    launch("setup" if args[:1] == ["setup"] else "")


if __name__ == "__main__":
    main()
