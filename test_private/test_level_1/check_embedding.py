import pickle

with open("application/indexes/local-folder/index.pkl", "rb") as f:
    data = pickle.load(f)

docstore = data[0]
index_to_doc_id = data[1]

docs_dict = docstore._dict

print(type(docs_dict))
print(len(docs_dict))

first_doc = list(docs_dict.values())[0]

print(type(first_doc))
print(first_doc.page_content[:500])
print(first_doc.metadata)

print(list(index_to_doc_id.items())[:5])