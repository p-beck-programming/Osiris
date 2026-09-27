from app.semantic.search import semantic_search


query = "Is this mother fucker functional at all in red rocks or Tennessee"

results = semantic_search(query, limit=5)

print()
print(f"Query: {query}")
print()

for result in results:
    print("=" * 60)
    print(f"Score: {result['score']:.3f}")
    print(f"Idea:  {result['idea_title']}")
    print(f"Note:  {result['content']}")
