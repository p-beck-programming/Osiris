import sys

from app.semantic.search import semantic_search


def main():
    if len(sys.argv) < 2:
        print('Usage: python -m app.semantic.cli "your search query"')
        return

    query = " ".join(sys.argv[1:])
    results = semantic_search(query, limit=5)

    print(f"\nQuery: {query}\n")

    for result in results:
        print("=" * 60)
        print(f"Score: {result['score']:.3f}")
        print(f"Idea:  {result['idea_title']}")
        print(f"Note:  {result['content']}")


if __name__ == "__main__":
    main()
