import json, sys
kind, prompt = sys.argv[1], " ".join(sys.argv[2:])
p = "sentinel/corpus.json"
data = json.load(open(p))
data.setdefault(kind, []).append(prompt)
json.dump(data, open(p, "w"), indent=2)
print("added:", kind, prompt)
