try:
    from src.utils.config import WINDOW_TITLE
except ModuleNotFoundError:
    from utils.config import WINDOW_TITLE


def main() -> None:
    print(f"{WINDOW_TITLE} setup is ready.")
    print("Next: connect teammate UI and start frame extraction pipeline.")


if __name__ == "__main__":
    main()
